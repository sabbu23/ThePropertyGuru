from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q, OuterRef
from django.core.paginator import Paginator
from .forms import UserSignupForm, UserProfileForm, SellerVerificationForm, PropertyForm, PropertyImageForm
from .models import UserProfile, SellerVerification, Notification, Property, PropertyImage, Favorite, PROPERTY_TYPES, \
    PROPERTY_PURPOSES, PROPERTY_STATUS, CITIES
from .models import PropertyView

from django.db.models import Count, Max
from .models import Conversation, Message

from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required


def is_admin(user):
    # Allow Django superusers to access admin features
    if user.is_superuser or user.is_staff:
        return True

    # Also check for users with admin role in profile
    try:
        return user.is_authenticated and user.profile.role == 'admin'
    except UserProfile.DoesNotExist:
        return False


def signup_view(request):
    if request.method == 'POST':
        user_form = UserSignupForm(request.POST)
        profile_form = UserProfileForm(request.POST)

        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()

            # Create user profile with selected role
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.role = user_form.cleaned_data.get('role')

            # If role is buyer, automatically verify
            if profile.role == 'buyer':
                profile.is_verified = True

            profile.save()

            # If seller, redirect to verification page
            if profile.role == 'seller':
                login(request, user)
                messages.info(request, "Please complete your seller verification.")
                return redirect('seller_verification')

            # For buyers, log them in and redirect to home
            login(request, user)
            messages.success(request, f"Account created for {user.username}!")
            return redirect('home')
    else:
        user_form = UserSignupForm()
        profile_form = UserProfileForm()

    return render(request, 'app/signup.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Log the user in regardless of verification status
            login(request, user)

            # Handle staff/superuser special case for admin access
            if user.is_staff or user.is_superuser or (hasattr(user, 'profile') and user.profile.role == 'admin'):
                return redirect('admin_dashboard')  # redirects admins to the dashboard

            try:
                profile = user.profile
                # If seller is not verified, add a message but still redirect to home
                if profile.role == 'seller' and not profile.is_verified:
                    try:
                        verification = profile.verification
                        if verification.status == 'pending':
                            messages.warning(request, "Your seller account is pending verification by an admin.")
                        elif verification.status == 'rejected':
                            messages.error(request,
                                           "Your seller verification was rejected. Please resubmit with improved documentation.")
                    except SellerVerification.DoesNotExist:
                        pass  # No need to handle this case as verification is mandatory during signup

                # Always redirect to home page regardless of role
                return redirect('home')

            except UserProfile.DoesNotExist:
                # Auto-create profile for user if it doesn't exist (for migration purposes)
                UserProfile.objects.create(
                    user=user,
                    role='buyer',  # Default role
                    is_verified=True
                )
                return redirect('home')
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'app/login.html')


@login_required
def seller_verification_view(request):
    # Check if user is a seller
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'seller':
        messages.error(request, "Only sellers need verification.")
        return redirect('home')

    # Check if already verified
    if request.user.profile.is_verified:
        messages.info(request, "Your account is already verified.")
        return redirect('home')

    # Get previous verification if it exists
    previous_verification = None
    verification_status = None
    try:
        previous_verification = request.user.profile.verification
        verification_status = previous_verification.status
        # If status is approved, don't allow resubmission
        if previous_verification.status == 'approved':
            request.user.profile.is_verified = True
            request.user.profile.save()
            messages.info(request, "Your account is already verified.")
            return redirect('home')
    except SellerVerification.DoesNotExist:
        pass

    # Check for rejected status to show appropriate message
    rejection_message = None
    if previous_verification and previous_verification.status == 'rejected':
        rejection_message = previous_verification.rejection_reason

    if request.method == 'POST':
        form = SellerVerificationForm(request.POST, request.FILES, instance=previous_verification)
        if form.is_valid():
            verification = form.save(commit=False)
            verification.seller = request.user.profile
            verification.status = 'pending'  # Reset to pending for resubmissions
            verification.approved = False
            verification.save()

            # Mark any related notifications as read
            Notification.objects.filter(
                user=request.user,
                message__contains="verification has been rejected"
            ).update(is_read=True)

            messages.success(request, "Your verification documents have been submitted and are pending approval.")
            return redirect('home')
    else:
        form = SellerVerificationForm(instance=previous_verification)

    return render(request, 'app/seller_verification.html', {
        'form': form,
        'is_resubmission': previous_verification is not None,
        'rejection_message': rejection_message,
        'verification_status': verification_status
    })


@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    # Create UserProfile for superuser if it doesn't exist
    if not hasattr(request.user, 'profile'):
        UserProfile.objects.create(
            user=request.user,
            role='admin',
            is_verified=True
        )

    # Get seller verifications by status
    pending_verifications = SellerVerification.objects.filter(status='pending')
    approved_verifications = SellerVerification.objects.filter(status='approved')
    rejected_verifications = SellerVerification.objects.filter(status='rejected')

    # Get property counts
    total_properties = Property.objects.count()
    active_properties = Property.objects.filter(is_active=True).count()
    inactive_properties = Property.objects.filter(is_active=False).count()

    # Get user counts
    total_users = User.objects.count()
    total_buyers = UserProfile.objects.filter(role='buyer').count()
    total_sellers = UserProfile.objects.filter(role='seller').count()
    verified_sellers = UserProfile.objects.filter(role='seller', is_verified=True).count()

    return render(request, 'app/admin_dashboard.html', {
        'pending_verifications': pending_verifications,
        'approved_verifications': approved_verifications,
        'rejected_verifications': rejected_verifications,
        'total_properties': total_properties,
        'active_properties': active_properties,
        'inactive_properties': inactive_properties,
        'total_users': total_users,
        'total_buyers': total_buyers,
        'total_sellers': total_sellers,
        'verified_sellers': verified_sellers
    })


@login_required
@user_passes_test(is_admin)
def approve_seller(request, verification_id):
    verification = get_object_or_404(SellerVerification, id=verification_id)

    # Update verification status
    verification.status = 'approved'
    verification.approved = True
    verification.approved_by = request.user
    verification.approved_at = timezone.now()
    verification.save()

    # Update seller profile
    seller_profile = verification.seller
    seller_profile.is_verified = True
    seller_profile.save()

    # Create notification for the seller
    Notification.objects.create(
        user=verification.seller.user,
        message="Congratulations! Your seller account has been verified. You can now list properties on our platform."
    )

    messages.success(request, f"Seller {seller_profile.user.username} has been approved.")
    return redirect('admin_dashboard')


@login_required
@user_passes_test(is_admin)
def reject_seller(request, verification_id):
    verification = get_object_or_404(SellerVerification, id=verification_id)

    if request.method == 'POST':
        # Get rejection reason from form
        rejection_reason = request.POST.get('rejection_reason', '')

        # Update verification status
        verification.status = 'rejected'
        verification.approved = False
        verification.rejection_reason = rejection_reason
        verification.rejected_at = timezone.now()
        verification.rejected_by = request.user
        verification.save()

        # Create notification for the seller
        Notification.objects.create(
            user=verification.seller.user,
            message=f"Your seller verification has been rejected. Reason: {rejection_reason}. Please update your documents and resubmit."
        )

        messages.success(request, "Seller application has been rejected and the seller has been notified.")
        return redirect('admin_dashboard')

    # If GET request, show rejection form
    return render(request, 'app/reject_seller.html', {
        'verification': verification
    })


def home_view(request):
    # Check if the user is a seller and show verification status
    verification_status = None
    rejection_message = None

    if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.role == 'seller':
        # If seller is not verified, check for pending or rejected status
        if not request.user.profile.is_verified:
            try:
                verification = request.user.profile.verification
                if verification.status == 'pending':
                    verification_status = 'pending'
                elif verification.status == 'rejected':
                    verification_status = 'rejected'
                    rejection_message = verification.rejection_reason
            except SellerVerification.DoesNotExist:
                # No verification submitted yet
                verification_status = 'not_submitted'

    # Get popular properties (those with most views)
    popular_properties = Property.objects.filter(is_active=True).annotate(
        view_count=Count('views')
    ).order_by('-view_count')[:3]  # Get top 3 most viewed properties

    # Get user's favorite property IDs for highlighting
    favorite_ids = []
    if request.user.is_authenticated:
        favorite_ids = Favorite.objects.filter(user=request.user).values_list('property_id', flat=True)

    return render(request, 'app/home.html', {
        'verification_status': verification_status,
        'rejection_message': rejection_message,
        'popular_properties': popular_properties,
        'favorite_ids': favorite_ids
    })


@login_required
def seller_dashboard(request):
    # Check if the user is a verified seller
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'seller':
        messages.error(request, "You must be a seller to access this page.")
        return redirect('home')

    if not request.user.profile.is_verified:
        messages.warning(request, "Your seller account is pending verification.")
        return redirect('home')

    # Get seller's properties
    properties = Property.objects.filter(seller=request.user.profile).order_by('-created_at')[:5]

    # Calculate dashboard statistics
    total_properties = Property.objects.filter(seller=request.user.profile).count()
    active_properties = Property.objects.filter(seller=request.user.profile, is_active=True).count()
    available_properties = Property.objects.filter(seller=request.user.profile, status='available').count()
    sold_properties = Property.objects.filter(seller=request.user.profile, status='sold').count()

    # Count total favorites on this seller's properties
    favorited_count = Favorite.objects.filter(property__seller=request.user.profile).count()

    # Count total views on this seller's properties
    total_views = PropertyView.objects.filter(property__seller=request.user.profile).count()

    return render(request, 'app/seller.html', {
        'properties': properties,
        'total_properties': total_properties,
        'active_properties': active_properties,
        'available_properties': available_properties,
        'sold_properties': sold_properties,
        'favorited_count': favorited_count,
        'total_views': total_views
    })


@login_required
def seller_verification_details(request, verification_id):
    """API endpoint to get verification details for the modal"""
    verification = get_object_or_404(SellerVerification, id=verification_id)

    # Get formatted dates
    submitted_at = verification.submitted_at.strftime("%b %d, %Y")
    approved_at = verification.approved_at.strftime("%b %d, %Y") if verification.approved_at else None
    rejected_at = verification.rejected_at.strftime("%b %d, %Y") if verification.rejected_at else None

    data = {
        'username': verification.seller.user.username,
        'email': verification.seller.user.email,
        'phone': verification.seller.phone or 'Not provided',
        'address': verification.seller.address or 'Not provided',
        'submitted_at': submitted_at,
        'profile_picture': verification.profile_picture.url,
        'identity_proof': verification.identity_proof.url,
        'status': verification.status,
        'approved_at': approved_at,
        'rejected_at': rejected_at,
        'rejection_reason': verification.rejection_reason,
        'rejected_by': verification.rejected_by.username if verification.rejected_by else None,
    }

    return JsonResponse(data)


@login_required
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()

    # Redirect back to the referring page
    return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required
def mark_all_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)

    # Redirect back to the referring page
    return redirect(request.META.get('HTTP_REFERER', 'home'))


# Property management views


@login_required
def property_list(request):
    """View all properties with filters"""
    # Start with all active properties
    properties = Property.objects.filter(is_active=True)

    # Get search parameter
    search = request.GET.get('search', '')

    # Apply search if provided
    if search:
        properties = properties.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(address__icontains=search) |
            Q(city__icontains=search)
        )

    # Apply filters if provided
    property_type = request.GET.get('property_type', '')
    purpose = request.GET.get('purpose', '')
    city = request.GET.get('city', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    min_area = request.GET.get('min_area', '')
    max_area = request.GET.get('max_area', '')
    min_bedrooms = request.GET.get('min_bedrooms', '')
    max_bedrooms = request.GET.get('max_bedrooms', '')
    min_bathrooms = request.GET.get('min_bathrooms', '')
    max_bathrooms = request.GET.get('max_bathrooms', '')
    sort = request.GET.get('sort', 'newest')

    if property_type:
        properties = properties.filter(property_type=property_type)

    if purpose:
        properties = properties.filter(purpose=purpose)

    if city:
        properties = properties.filter(city__icontains=city)

    if min_price:
        properties = properties.filter(price__gte=min_price)

    if max_price:
        properties = properties.filter(price__lte=max_price)

    if min_area:
        properties = properties.filter(area_size__gte=min_area)

    if max_area:
        properties = properties.filter(area_size__lte=max_area)

    if min_bedrooms:
        properties = properties.filter(bedrooms__gte=min_bedrooms)

    if max_bedrooms:
        properties = properties.filter(bedrooms__lte=max_bedrooms)

    if min_bathrooms:
        properties = properties.filter(bathrooms__gte=min_bathrooms)

    if max_bathrooms:
        properties = properties.filter(bathrooms__lte=max_bathrooms)

    # Apply sorting
    if sort == 'price_low':
        properties = properties.order_by('price')
    elif sort == 'price_high':
        properties = properties.order_by('-price')
    elif sort == 'area_low':
        properties = properties.order_by('area_size')
    elif sort == 'area_high':
        properties = properties.order_by('-area_size')
    else:  # Default: newest
        properties = properties.order_by('-created_at')

    # Get user's favorite property IDs for highlighting
    favorite_ids = []
    if request.user.is_authenticated:
        favorite_ids = Favorite.objects.filter(user=request.user).values_list('property_id', flat=True)

    # Paginate results
    paginator = Paginator(properties, 9)  # Show 9 properties per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'app/property_list.html', {
        'properties': page_obj,
        'property_types': PROPERTY_TYPES,
        'property_purposes': PROPERTY_PURPOSES,
        'favorite_ids': favorite_ids,
        'search': search,
        'sort': sort,
        'is_paginated': paginator.num_pages > 1,
        'page_obj': page_obj
    })


def property_detail(request, property_id):
    """View details of a specific property"""
    property = get_object_or_404(Property, id=property_id, is_active=True)

    # Check if property is in user's favorites
    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = Favorite.objects.filter(user=request.user, property=property).exists()

    # Only track view if user is authenticated and not the property owner
    if request.user.is_authenticated:
        # Don't track if the viewer is the property owner
        if request.user != property.seller.user:
            # Check if this user has already viewed this property
            _, created = PropertyView.objects.get_or_create(
                property=property,
                user=request.user
            )
            # If created is True, this is a new view
    # For anonymous users, we won't track views as requested

    return render(request, 'app/property_detail.html', {
        'property': property,
        'is_favorite': is_favorite
    })


@login_required
def buy_properties(request):
    """View properties for sale with filters"""
    # Start with all active properties for sale
    properties = Property.objects.filter(is_active=True, purpose='sale')

    # Get search parameter
    search = request.GET.get('search', '')

    # Apply search if provided
    if search:
        properties = properties.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(address__icontains=search) |
            Q(city__icontains=search)
        )

    # Apply filters if provided
    property_type = request.GET.get('property_type', '')
    city = request.GET.get('city', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    min_area = request.GET.get('min_area', '')
    max_area = request.GET.get('max_area', '')
    min_bedrooms = request.GET.get('min_bedrooms', '')
    max_bedrooms = request.GET.get('max_bedrooms', '')
    min_bathrooms = request.GET.get('min_bathrooms', '')
    max_bathrooms = request.GET.get('max_bathrooms', '')
    sort = request.GET.get('sort', 'newest')

    if property_type:
        properties = properties.filter(property_type=property_type)

    if city:
        properties = properties.filter(city__icontains=city)

    if min_price:
        properties = properties.filter(price__gte=min_price)

    if max_price:
        properties = properties.filter(price__lte=max_price)

    if min_area:
        properties = properties.filter(area_size__gte=min_area)

    if max_area:
        properties = properties.filter(area_size__lte=max_area)

    if min_bedrooms:
        properties = properties.filter(bedrooms__gte=min_bedrooms)

    if max_bedrooms:
        properties = properties.filter(bedrooms__lte=max_bedrooms)

    if min_bathrooms:
        properties = properties.filter(bathrooms__gte=min_bathrooms)

    if max_bathrooms:
        properties = properties.filter(bathrooms__lte=max_bathrooms)

    # Apply sorting
    if sort == 'price_low':
        properties = properties.order_by('price')
    elif sort == 'price_high':
        properties = properties.order_by('-price')
    elif sort == 'area_low':
        properties = properties.order_by('area_size')
    elif sort == 'area_high':
        properties = properties.order_by('-area_size')
    else:  # Default: newest
        properties = properties.order_by('-created_at')

    # Get user's favorite property IDs for highlighting
    favorite_ids = []
    if request.user.is_authenticated:
        favorite_ids = Favorite.objects.filter(user=request.user).values_list('property_id', flat=True)

    # Paginate results
    paginator = Paginator(properties, 9)  # Show 9 properties per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'app/buy.html', {
        'properties': page_obj,
        'property_types': PROPERTY_TYPES,
        'favorite_ids': favorite_ids,
        'search': search,
        'sort': sort,
        'is_paginated': paginator.num_pages > 1,
        'page_obj': page_obj
    })


@login_required
def rent_properties(request):
    """View properties for rent with filters"""
    # Start with all active properties for rent
    properties = Property.objects.filter(is_active=True, purpose='rent')

    # Get search parameter
    search = request.GET.get('search', '')

    # Apply search if provided
    if search:
        properties = properties.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(address__icontains=search) |
            Q(city__icontains=search)
        )

    # Apply filters if provided
    property_type = request.GET.get('property_type', '')
    city = request.GET.get('city', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    min_area = request.GET.get('min_area', '')
    max_area = request.GET.get('max_area', '')
    min_bedrooms = request.GET.get('min_bedrooms', '')
    max_bedrooms = request.GET.get('max_bedrooms', '')
    min_bathrooms = request.GET.get('min_bathrooms', '')
    max_bathrooms = request.GET.get('max_bathrooms', '')
    sort = request.GET.get('sort', 'newest')

    if property_type:
        properties = properties.filter(property_type=property_type)

    if city:
        properties = properties.filter(city__icontains=city)

    if min_price:
        properties = properties.filter(price__gte=min_price)

    if max_price:
        properties = properties.filter(price__lte=max_price)

    if min_area:
        properties = properties.filter(area_size__gte=min_area)

    if max_area:
        properties = properties.filter(area_size__lte=max_area)

    if min_bedrooms:
        properties = properties.filter(bedrooms__gte=min_bedrooms)

    if max_bedrooms:
        properties = properties.filter(bedrooms__lte=max_bedrooms)

    if min_bathrooms:
        properties = properties.filter(bathrooms__gte=min_bathrooms)

    if max_bathrooms:
        properties = properties.filter(bathrooms__lte=max_bathrooms)

    # Apply sorting
    if sort == 'price_low':
        properties = properties.order_by('price')
    elif sort == 'price_high':
        properties = properties.order_by('-price')
    elif sort == 'area_low':
        properties = properties.order_by('area_size')
    elif sort == 'area_high':
        properties = properties.order_by('-area_size')
    else:  # Default: newest
        properties = properties.order_by('-created_at')

    # Get user's favorite property IDs for highlighting
    favorite_ids = []
    if request.user.is_authenticated:
        favorite_ids = Favorite.objects.filter(user=request.user).values_list('property_id', flat=True)

    # Paginate results
    paginator = Paginator(properties, 9)  # Show 9 properties per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'app/rent.html', {
        'properties': page_obj,
        'property_types': PROPERTY_TYPES,
        'favorite_ids': favorite_ids,
        'search': search,
        'sort': sort,
        'is_paginated': paginator.num_pages > 1,
        'page_obj': page_obj
    })


@login_required
def add_property(request):
    """Add a new property"""
    # Check if user is a verified seller
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'seller':
        messages.error(request, "You must be a seller to add properties.")
        return redirect('home')

    if not request.user.profile.is_verified:
        messages.warning(request, "Your seller account is pending verification.")
        return redirect('home')

    if request.method == 'POST':
        form = PropertyForm(request.POST)
        if form.is_valid():
            # Create new property with seller information
            property = form.save(commit=False)
            property.seller = request.user.profile
            property.save()

            # Add success message
            messages.success(request, "Property added successfully! Now add some images.")

            # Redirect to image upload page
            return redirect('upload_property_image', property_id=property.id)
    else:
        form = PropertyForm()

    return render(request, 'app/add_property.html', {
        'form': form,
        'property_types': PROPERTY_TYPES,
        'property_purposes': PROPERTY_PURPOSES,
        'CITIES': CITIES
    })


@login_required
def edit_property(request, property_id):
    """Edit an existing property"""
    property = get_object_or_404(Property, id=property_id)

    # Check if user is the seller of this property
    if property.seller.user != request.user:
        messages.error(request, "You can only edit your own properties.")
        return redirect('manage_properties')

    if request.method == 'POST':
        form = PropertyForm(request.POST, instance=property)
        if form.is_valid():
            form.save()
            messages.success(request, "Property updated successfully!")
            return redirect('manage_properties')
    else:
        form = PropertyForm(instance=property)

    return render(request, 'app/edit_property.html', {
        'form': form,
        'property': property,
        'property_types': PROPERTY_TYPES,
        'property_purposes': PROPERTY_PURPOSES
    })


@login_required
def delete_property(request, property_id):
    """Delete a property"""
    property = get_object_or_404(Property, id=property_id)

    # Check if user is the seller of this property
    if property.seller.user != request.user:
        messages.error(request, "You can only delete your own properties.")
        return redirect('manage_properties')

    if request.method == 'POST':
        property.delete()
        messages.success(request, "Property deleted successfully!")
        return redirect('manage_properties')

    return render(request, 'app/delete_property_confirmation.html', {
        'property': property
    })


@login_required
def upload_property_image(request, property_id):
    """Upload images for a property"""
    # Use hardcoded property_id to prevent errors
    property = get_object_or_404(Property, id=property_id)

    # Check if user is the seller of this property
    if property.seller.user != request.user:
        messages.error(request, "You can only add images to your own properties.")
        return redirect('manage_properties')

    if request.method == 'POST':
        form = PropertyImageForm(request.POST, request.FILES)
        if form.is_valid():
            # Create a new PropertyImage instance
            image = PropertyImage()
            image.property = property
            image.image = request.FILES['image']
            image.is_primary = 'is_primary' in request.POST

            # If this is set as primary, unset any existing primary images
            if image.is_primary:
                PropertyImage.objects.filter(property=property, is_primary=True).update(is_primary=False)

            # If this is the first image, make it primary
            elif not PropertyImage.objects.filter(property=property).exists():
                image.is_primary = True

            image.save()
            messages.success(request, "Image uploaded successfully!")
            return redirect('upload_property_image', property_id=property.id)
    else:
        form = PropertyImageForm()

    return render(request, 'app/property_image_upload.html', {
        'form': form,
        'property': property
    })


@login_required
def delete_property_image(request, image_id):
    """Delete a property image"""
    image = get_object_or_404(PropertyImage, id=image_id)
    property = image.property

    # Check if user is the seller of this property
    if property.seller.user != request.user:
        messages.error(request, "You can only delete images from your own properties.")
        return redirect('manage_properties')

    was_primary = image.is_primary
    image.delete()

    # If the deleted image was primary, set another image as primary
    if was_primary:
        first_image = PropertyImage.objects.filter(property=property).first()
        if first_image:
            first_image.is_primary = True
            first_image.save()

    messages.success(request, "Image deleted successfully!")
    return redirect('upload_property_image', property_id=property.id)


@login_required
def set_primary_image(request, image_id):
    """Set an image as the primary image for a property"""
    image = get_object_or_404(PropertyImage, id=image_id)
    property = image.property

    # Check if user is the seller of this property
    if property.seller.user != request.user:
        messages.error(request, "You can only modify images of your own properties.")
        return redirect('manage_properties')

    # Unset any existing primary images
    PropertyImage.objects.filter(property=property, is_primary=True).update(is_primary=False)

    # Set this image as primary
    image.is_primary = True
    image.save()

    messages.success(request, "Primary image updated successfully!")
    return redirect('upload_property_image', property_id=property.id)


@login_required
def manage_properties(request):
    """Manage user's properties"""
    # Check if user is a seller
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'seller':
        messages.error(request, "Only sellers can manage properties.")
        return redirect('home')

    if not request.user.profile.is_verified:
        messages.warning(request, "Your seller account is pending verification.")
        return redirect('home')

    # Get user's properties
    properties = Property.objects.filter(seller=request.user.profile).order_by('-created_at')

    # Paginate results
    paginator = Paginator(properties, 10)  # Show 10 properties per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'app/manage_properties.html', {
        'properties': page_obj,
        'is_paginated': paginator.num_pages > 1,
        'page_obj': page_obj
    })


@login_required
def toggle_favorite(request, property_id):
    """Toggle a property as favorite"""
    property = get_object_or_404(Property, id=property_id)

    # Check if property is already a favorite
    favorite = Favorite.objects.filter(user=request.user, property=property).first()

    if favorite:
        # Remove from favorites
        favorite.delete()
        messages.success(request, "Property removed from favorites.")
    else:
        # Add to favorites
        Favorite.objects.create(user=request.user, property=property)
        messages.success(request, "Property added to favorites.")

    # Redirect back to the referring page
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    else:
        return redirect('property_detail', property_id=property_id)


@login_required
def my_favorites(request):
    """View user's favorite properties"""
    # Get user's favorites
    favorites = Favorite.objects.filter(user=request.user).select_related('property').order_by('-added_at')

    # Extract properties from favorites
    favorite_properties = [favorite.property for favorite in favorites if favorite.property.is_active]

    # Paginate results
    paginator = Paginator(favorite_properties, 9)  # Show 9 properties per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Get favorite IDs for highlighting
    favorite_ids = [prop.id for prop in favorite_properties]

    return render(request, 'app/my_favorites.html', {
        'properties': page_obj,
        'favorite_ids': favorite_ids,
        'is_paginated': paginator.num_pages > 1,
        'page_obj': page_obj
    })


@login_required
def edit_property_image(request, image_id):
    """Edit a property image"""
    image = get_object_or_404(PropertyImage, id=image_id)
    property = image.property

    # Check if user is the seller of this property
    if property.seller.user != request.user:
        messages.error(request, "You can only edit images of your own properties.")
        return redirect('manage_properties')

    if request.method == 'POST':
        form = PropertyImageForm(request.POST, request.FILES, instance=image)
        if form.is_valid():
            form.save()
            messages.success(request, "Image updated successfully!")
            return redirect('upload_property_image', property_id=property.id)
    else:
        form = PropertyImageForm(instance=image)

    return render(request, 'app/edit_property_image.html', {
        'form': form,
        'property': property,
        'image': image
    })


@login_required
def toggle_property_status(request, property_id):
    """Toggle a property's status between available and sold"""
    property = get_object_or_404(Property, id=property_id)

    # Check if user is the seller of this property
    if property.seller.user != request.user:
        messages.error(request, "You can only modify your own properties.")
        return redirect('manage_properties')

    # Toggle status
    property.status = 'sold' if property.status == 'available' else 'available'
    property.save()

    messages.success(request, f"Property status updated to {property.get_status_display()}")
    return redirect('manage_properties')


@login_required
def inbox(request):
    """View all conversations for the logged-in user"""
    # Get all conversations for the current user, ordered by most recent message
    conversations = Conversation.objects.filter(participants=request.user).order_by('-last_message_at')

    # Add the unread count and other participant info in Python
    conversation_list = []

    for conversation in conversations:
        # Get the other participant
        other_user = conversation.get_other_participant(request.user)

        # Count unread messages from the other participant
        unread_count = Message.objects.filter(
            conversation=conversation,
            sender=other_user,
            is_read=False
        ).count()

        # Add unread_count as an attribute
        conversation.unread_count = unread_count
        conversation_list.append(conversation)

    return render(request, 'app/inbox.html', {
        'conversations': conversation_list
    })


@login_required
def conversation_detail(request, conversation_id):
    """View a specific conversation and its messages"""
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    other_user = conversation.get_other_participant(request.user)

    # Mark all messages as read when viewing the conversation
    unread_messages = Message.objects.filter(
        conversation=conversation,
        sender=other_user,
        is_read=False
    )
    unread_messages.update(is_read=True)

    # Handle new message submission
    if request.method == 'POST':
        content = request.POST.get('content')
        if content and content.strip():
            message = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=content.strip()
            )

            # Update conversation's last_message_at
            conversation.last_message_at = timezone.now()
            conversation.save()

            # If using AJAX submission, return JSON response
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': {
                        'id': message.id,
                        'content': message.content,
                        'timestamp': message.timestamp.strftime('%b %d, %Y, %I:%M %p'),
                        'sender_id': message.sender.id,
                        'sender_name': message.sender.username,
                        'is_sender': True
                    }
                })

            # Redirect to avoid form resubmission
            return redirect('conversation_detail', conversation_id=conversation.id)

    # Get all messages for this conversation, ordered by timestamp
    messages_list = conversation.messages.order_by('timestamp')

    return render(request, 'app/conversation_detail.html', {
        'conversation': conversation,
        'messages': messages_list,
        'other_user': other_user,
        'property': conversation.property
    })


@login_required
def start_conversation(request, user_id, property_id=None):
    """Start a new conversation with another user, optionally about a property"""
    other_user = get_object_or_404(User, id=user_id)
    property_obj = None

    # Don't allow starting conversation with yourself
    if other_user == request.user:
        messages.error(request, "You cannot start a conversation with yourself.")
        return redirect('home')

    # Check if property_id is provided and exists
    if property_id:
        property_obj = get_object_or_404(Property, id=property_id)

    # Check if a conversation already exists between these users
    existing_conversation = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    )

    # If property specified, further filter by property
    if property_obj:
        existing_conversation = existing_conversation.filter(property=property_obj)

    # Get the first conversation if any exists
    existing_conversation = existing_conversation.first()

    if existing_conversation:
        # Redirect to existing conversation
        return redirect('conversation_detail', conversation_id=existing_conversation.id)

    # Create new conversation
    conversation = Conversation.objects.create()
    conversation.participants.add(request.user, other_user)

    if property_obj:
        conversation.property = property_obj
        conversation.save()

    # If initial message is provided, create it
    if request.method == 'POST':
        content = request.POST.get('content')
        if content and content.strip():
            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=content
            )

    return redirect('conversation_detail', conversation_id=conversation.id)


@login_required
def check_new_messages(request, conversation_id):
    """API endpoint to check for new messages in a conversation"""
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    other_user = conversation.get_other_participant(request.user)

    try:
        last_message_id = int(request.GET.get('last_message_id', 0))
    except ValueError:
        last_message_id = 0

    # Get messages newer than the last seen message
    new_messages = conversation.messages.filter(id__gt=last_message_id)

    # Mark messages as read if they were sent by the other user
    unread_messages = new_messages.filter(sender=other_user, is_read=False)
    if unread_messages.exists():
        unread_messages.update(is_read=True)

    # Prepare JSON response
    messages_data = []
    for message in new_messages:
        messages_data.append({
            'id': message.id,
            'content': message.content,
            'timestamp': message.timestamp.strftime('%b %d, %Y, %I:%M %p'),
            'sender_id': message.sender.id,
            'sender_name': message.sender.username,
            'is_sender': message.sender == request.user
        })

    return JsonResponse({'messages': messages_data})


@login_required
def unread_message_count(request):
    """API endpoint to get the total unread message count for the user"""
    count = Message.objects.filter(
        conversation__participants=request.user,  # Messages in conversations the user is part of
        is_read=False
    ).exclude(
        sender=request.user  # Exclude messages sent by the user themselves
    ).count()

    return JsonResponse({'unread_count': count})


# for viewing user profile in chat
@login_required
def user_profile_view(request, user_id):
    """View to display a user's profile"""
    profile_user = get_object_or_404(User, id=user_id)

    # Check if this is a seller with verification
    is_verified_seller = False
    seller_verification = None

    if hasattr(profile_user, 'profile') and profile_user.profile.role == 'seller':
        if profile_user.profile.is_verified:
            is_verified_seller = True

        # Try to get verification details if they exist
        try:
            seller_verification = profile_user.profile.verification
        except SellerVerification.DoesNotExist:
            pass

    # Get user's properties if they are a seller
    properties = []
    if hasattr(profile_user, 'profile') and profile_user.profile.role == 'seller':
        properties = Property.objects.filter(seller=profile_user.profile, is_active=True)[:4]

    return render(request, 'app/user_profile.html', {
        'profile_user': profile_user,
        'is_verified_seller': is_verified_seller,
        'seller_verification': seller_verification,
        'properties': properties,
    })


@require_GET
@login_required
def get_csrf_token(request):
    """View to refresh CSRF token via AJAX."""
    csrf_token = get_token(request)
    return JsonResponse({'csrf_token': csrf_token})
