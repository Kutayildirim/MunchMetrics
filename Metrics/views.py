from django.shortcuts import render, redirect
from django.views import View
from django.core.paginator import Paginator
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .forms import RestaurantForm, MealForm, RegisterForm, RestaurantRateForm, MealRateForm, UpdateForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from .models import Restaurant, Meal, Profile, ReviewMeal, ReviewRestaurant, CUISINES
import random
from django.db.models import Avg, Count


class IndexView(View):
    def get(self, request):
        restaurant_queryset = Restaurant.objects.all()
        sort_method = request.GET.get('sort')

        if sort_method:
            restaurant_queryset = restaurant_queryset.order_by(sort_method)
        else:
            restaurant_queryset = restaurant_queryset.order_by('name')

        cuisine_method = request.GET.get('cuisine')
        if cuisine_method:
            restaurant_queryset = restaurant_queryset.filter(cuisine=cuisine_method)
        search_method = request.GET.get('search')
        if search_method:
            restaurant_queryset = restaurant_queryset.filter(Q(name__icontains=search_method) |
                                                             Q(address__icontains=search_method) |
                                                             Q(description__icontains=search_method) |
                                                             Q(cuisine__icontains=search_method) |
                                                             Q(meal__name__icontains=search_method)).distinct()

        restaurant_queryset = restaurant_queryset.annotate(num_meals=Count('meal'))
        restaurant_queryset = restaurant_queryset.annotate(avg_price=Avg('meal__price'))

        restaurant_paginator = Paginator(restaurant_queryset, 9)
        page_num = request.GET.get('page')
        restaurant_page = restaurant_paginator.get_page(page_num)
        random_restaurant = None
        if restaurant_queryset:
            random_restaurant = random.choice(restaurant_queryset)

        context = {
            'restaurant_queryset': restaurant_queryset,
            'random_restaurant': random_restaurant,
            'cuisines': CUISINES,
            'restaurant_page': restaurant_page,
        }
        if request.GET.get('only_restaurants'):
            return render(request, "Metrics/restaurantajax.html", context)

        return render(request, "Metrics/restaurantindex.html", context)


class RestaurantDetailView(View):
    def post(self, request, restaurant_id):
        if request.user.is_authenticated:
            form = RestaurantRateForm(request.POST)
            if form.is_valid():
                review = form.save(commit=False)
                review.user = request.user
                review.restaurant_id = restaurant_id
                review.save()
                return redirect('Menu', restaurant_id=restaurant_id)
        else:
            messages.success(request, "You Must Be logged in to View this page ")

    def get(self, request, restaurant_id):

        restaurant = get_object_or_404(Restaurant, id=restaurant_id)
        if request.user.is_authenticated:
            form = RestaurantRateForm(request.POST)
        else:
            form = None

        context = {'meal_list': restaurant.meal_set.all(),
                   'restaurant': restaurant,
                   'form': form,
                   }
        return render(request, "Metrics/restaurantdetail.html", context)


class AddRestaurant(View):
    def get(self, request):
        form = RestaurantForm()
        context = {'form': form}
        return render(request, 'Metrics/restaurantform.html', context)

    def post(self, request):
        form = RestaurantForm(request.POST, request.FILES)
        if form.is_valid():
            restaurant = form.save(commit=False)
            restaurant.owner = request.user
            if Restaurant.objects.filter(name=restaurant.name, address=restaurant.address).exists():
                messages.error(request, "A restaurant with the same name already exists.")
                return redirect('AddRestaurant')
            restaurant.save()
            messages.success(request, "Added Successfully")
            return redirect('AddRestaurant')
        else:
            messages.error(request, "Invalid form data.")
            return redirect('AddRestaurant')


class UpdateRestaurant(View):
    def get(self, request, pk):
        restaurant = get_object_or_404(Restaurant, id=pk)
        if request.user == restaurant.owner or request.user.groups.filter(name="Administrator").exists():
            form = RestaurantForm(instance=restaurant)
            context = {'form': form, 'restaurant': restaurant}
            return render(request, 'Metrics/restaurantform.html', context)

        else:
            return redirect('index')

    def post(self, request, pk):
        restaurant = get_object_or_404(Restaurant, id=pk)
        if request.user == restaurant.owner or request.user.groups.filter(name="Administrator").exists():
            form = RestaurantForm(request.POST, request.FILES, instance=restaurant)
            if form.is_valid():
                new_restaurant = form.save(commit=False)
                existing_restaurant = Restaurant.objects.filter(name=new_restaurant.name,
                                                                address=new_restaurant.address)\
                                                        .exclude(id=restaurant.id).exists()
                if existing_restaurant:
                    messages.error(request, "A restaurant with the same name and address already exists.")
                    return redirect('UpdateRestaurant', pk=restaurant.id)

                form.save()
                messages.success(request, "Updated Successfully ")
                return redirect('Menu', restaurant_id=restaurant.id)
            else:
                return redirect('UpdateRestaurant', pk=restaurant.id)
        else:
            return redirect('index')


class DeleteRestaurant(View):
    def get(self, request, pk):
        restaurant = get_object_or_404(Restaurant, id=pk)
        if request.user == restaurant.owner or request.user.groups.filter(name="Administrator").exists():
            restaurant.delete()
        return redirect('index')


class DeleteRestaurantReviews(View):
    def get(self, request, pk):
        review = get_object_or_404(ReviewRestaurant, id=pk)
        if request.user == review.user or request.user.groups.filter(name="Administrator").exists():
            review.delete()
            messages.success(request, "Deleted Successfully ")
        return redirect(request.META.get('HTTP_REFERER'))


class AddMeal(View):
    def get(self, request):
        form = MealForm()
        if request.user.groups.filter(name="Administrator").exists():
            form = MealForm()
        else:
            form.fields['restaurant'].queryset = Restaurant.objects.filter(owner=request.user)
        meal_list = Meal.objects.all()
        context = {'form': form,
                   'meal_list': meal_list}
        return render(request, 'Metrics/mealform.html', context)

    def post(self, request):
        form = MealForm(request.POST, request.FILES)
        if form.is_valid():
            meal = form.save(commit=False)

            existing_meal = Meal.objects.filter(name=meal.name, restaurant=meal.restaurant).exists()
            if existing_meal:
                messages.error(request, f"A meal with the same name already exists in {meal.restaurant}.")
            else:
                meal.save()
                messages.success(request, "Added Successfully")
        else:
            messages.error(request, "Invalid form data.")

        return redirect('AddMeal')


class UpdateMeal(View):
    def get(self, request, pk):
        meal = get_object_or_404(Meal, id=pk)
        if request.user == meal.restaurant.owner or request.user.groups.filter(name="Administrator").exists():
            form = MealForm(instance=meal)
            context = {'form': form, 'meal': meal}
            return render(request, 'Metrics/mealform.html', context)
        else:
            messages.warning(request, "You Can't do that")
            return redirect(request.META.get('HTTP_REFERER'))

    def post(self, request, pk):
        meal = get_object_or_404(Meal, id=pk)
        if request.user == meal.restaurant.owner or request.user.groups.filter(name="Administrator").exists():
            form = MealForm(request.POST, request.FILES, instance=meal)
            if form.is_valid():
                new_meal = form.save(commit=False)

                existing_meal = Meal.objects.filter(name=new_meal.name, restaurant=meal.restaurant).exclude(
                    id=meal.id).exists()
                if existing_meal:
                    messages.error(request, f"A meal with the same name already exists in {meal.restaurant}.")
                    return redirect(request.META.get('HTTP_REFERER'))

                form.save()
                messages.success(request, "Updated Successfully ")
                return redirect(request.META.get('HTTP_REFERER'))
            else:
                return redirect('AddMeal')
        else:
            return redirect(request.META.get('HTTP_REFERER'))


class DeleteMeal(View):
    def get(self, request, pk):
        meal = get_object_or_404(Meal, id=pk)
        if request.user == meal.restaurant.owner or request.user.groups.filter(name="Administrator").exists():
            meal.delete()
        return redirect(request.META.get('HTTP_REFERER'))


class MealReviews(View):
    def post(self, request, meal_id):
        if request.user.is_authenticated:
            form = MealRateForm(request.POST)
            if form.is_valid():
                review = form.save(commit=False)
                review.user = request.user
                review.meal_id = meal_id
                review.save()
                return redirect('MealReviews', meal_id=meal_id)
            else:
                messages.success(request, "You Must Be logged in to View this page ")

    def get(self, request, meal_id):
        meal = get_object_or_404(Meal, id=meal_id)
        if request.user.is_authenticated:
            form = MealRateForm(request.POST)
        else:
            form = None
        context = {
            'meal': meal,
            'form': form,
        }
        return render(request, "Metrics/mealreviews.html", context)


class DeleteMealReviews(View):
    def get(self, request, pk):
        review = get_object_or_404(ReviewMeal, id=pk)
        if request.user == review.user or request.user.groups.filter(name="Administrator").exists():
            review.delete()
        return redirect(request.META.get('HTTP_REFERER'))


class ProfileView(View):
    def get(self, request, pk):
        if request.user.is_authenticated:
            profile = Profile.objects.get(user_id=pk)
            restaurant_list = Restaurant.objects.filter(owner=profile.user)
            context = {'profile': profile, 'restaurant_list': restaurant_list}

            return render(request, 'Metrics/profile.html', context)

        else:
            messages.success(request, "You Must Be logged in to View this page ")


class LoginUser(View):
    def get(self, request):
        return render(request, 'Metrics/login.html', {})

    def post(self, request):
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "Logged in Successfully")
            return redirect('index')
        else:
            messages.success(request, "Cannot Login, Please Try Again")
            return redirect('Login')


class LogoutUser(View):
    def get(self, request):
        logout(request)
        messages.success(request, "Logged Out Successfully See You in Your Next Munch")
        return redirect('index')


class Register(View):
    def get(self, request):
        form = RegisterForm
        return render(request, 'Metrics/register.html', {'form': form})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']

            user = authenticate(username=username, password=password)
            login(request, user)
            messages.success(request, "Register is Completed Welcome to MunchMetrics!")
            return redirect('index')

        else:
            messages.warning(request, "Register is not completed please try again")
            return redirect('Register')


class UpdateUser(View):
    def get(self, request):
        current_user = User.objects.get(id=request.user.id)
        form = UpdateForm(request.POST, instance=current_user)
        return render(request, 'Metrics/update_user.html', {'form': form})

    def post(self, request):
        if request.user.is_authenticated:
            current_user = User.objects.get(id=request.user.id)
            form = UpdateForm(request.POST, instance=current_user)
            if form.is_valid():
                form.save()
                messages.success(request, "Updated Successfully")

            return redirect('ProfileView')

        else:
            messages.success(request, "You must be logged in")
            return redirect('index')
