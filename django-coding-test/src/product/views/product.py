import base64
import json  # Import the json module
import os

from django.core.files.base import ContentFile
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count
from django.http import (HttpResponse, HttpResponseRedirect,
                         HttpResponseServerError, JsonResponse)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View, generic
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

from product.forms import ProductForm  # Import your product form
from product.models import (Product, ProductImage, ProductVariant,
                            ProductVariantPrice, Variant)


class ProductEditView(View):
    template_name = 'products/edit.html'
    model = Product
    success_url = '/product/list.html'

    def get(self, request, pk):
        # Retrieve the product based on the primary key (pk)
        product = get_object_or_404(Product, pk=pk)
        form = ProductForm(instance=product)
        context = {
            'product': product,
            'form': form,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        # Retrieve the product based on the primary key (pk)
        product = get_object_or_404(Product, pk=pk)
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('product:list.product'))
        context = {
            'product': product,
            'form': form,
        }
        return render(request, self.template_name, context)
    
    


class CreateProductView(View):
    template_name = 'products/create.html'
    model = Product
    queryset = Product.objects.all()
    success_url = '/product/list.html'
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        variants = Variant.objects.filter(active=True).values('id', 'title')
        context = {
            'product': True,
            'variants': list(variants)
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        try:
            # Parse JSON data sent from Vue.js
            data = json.loads(request.body.decode('utf-8'))
            # Extract product details
            product_name = data.get('title', '')  
            product_sku = data.get('sku', '')  
            description = data.get('description', '')  
            image_data = data.get('product_image', '')  

            # Create a new product
            product = Product.objects.create(
                title=product_name,
                sku=product_sku,
                description=description
            )
            product.save()
            
            if image_data:
                image_data = image_data.split(',')[1]  
                image_data = base64.b64decode(image_data)
                image_name = f"{product_sku}.png"  
                image_path = os.path.join('src/images', image_name)
                print("image path ", image_path)
                # Save the image to the specified directory
                with open(image_path, 'wb') as image_file:
                    image_file.write(image_data)

                ProductImage.objects.create(product=product, file=image_path)

            # Extract and create product variants
            product_variants = data.get('product_variant', [])
            for variant_data in product_variants:
                variant_id = variant_data.get('option', '')
                tags = variant_data.get('tags', '')
                
                concatenated_tags = ''
                for index, tag in enumerate(tags):
                    concatenated_tags += tag
                    if index < len(tags) - 1:
                        concatenated_tags += '/'

                tags = concatenated_tags
                
                active = variant_data.get('active', 1)
                
                # Create a Variant instance
                variant = Variant.objects.create(
                    title=tags,
                    description=description,
                    active=active
                )
                
                # Create a ProductVariant instance associated with the created Variant
                ProductVariant.objects.create(variant_title=tags, variant=variant, product=product)
            
            # Extract and create product variant prices
            product_variant_prices = data.get('product_variant_prices', [])
            for price_data in product_variant_prices:
                price = price_data.get('price', 0)
                stock = price_data.get('stock', 0)
                
                ProductVariantPrice.objects.create(
                    price=price,
                    stock=stock,
                    product=product,
                )
                
            return HttpResponseRedirect(reverse('product:list.product'))
        
        except Exception as e:
            print("Error:", e)
            return HttpResponseServerError("An error occurred while creating the product.")

        
class ProductListView(generic.ListView):
    model = Product
    template_name = 'products/list.html'
    context_object_name = 'products'
    paginate_by = 2 

    def get_queryset(self):
        queryset = Product.objects.order_by('id').all()

        title = self.request.GET.get('title')
        variant = self.request.GET.get('variant')
        price_from = self.request.GET.get('price_from')
        price_to = self.request.GET.get('price_to')
        date = self.request.GET.get('date')

        if title:
            queryset = queryset.filter(title__icontains=title)
        if variant:
            queryset = queryset.filter(productvariant__variant__description__icontains=variant)
        if price_from:
            queryset = queryset.filter(productvariantprice__price__gte=price_from)
        if price_to:
            queryset = queryset.filter(productvariantprice__price__lte=price_to)
        if date:
            queryset = queryset.filter(created_at=date)
        # print(queryset.query)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        paginator = Paginator(self.get_queryset(), self.paginate_by)
        page_number = self.request.GET.get('page')
        
        try:
            page = paginator.page(page_number)
        except PageNotAnInteger:
            page = paginator.page(1)
        except EmptyPage:
            page = paginator.page(paginator.num_pages)
        
        total_products = paginator.count
        
        start_index = (page.number - 1) * self.paginate_by + 1
        end_index = min(start_index + self.paginate_by - 1, total_products)
        
        
        
        variants = Variant.objects.all()

        # Create a dictionary to hold variant data
        variant_data = {}

        for variant in variants:
            variant_id = variant.id
            variant_name = variant.title
            variant_titles = ProductVariant.objects.filter(variant=variant_id).values_list('variant_title', flat=True).distinct()
            variant_data[variant_name] = list(variant_titles)

        context['variant_data'] = variant_data
        
        context['products'] = page
        context['message'] = f"Showing {start_index} to {end_index} out of {total_products}"

        return context
