import json
import requests
from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.urls import reverse
from django.http import JsonResponse
from reference.models import Source
from .forms import SetupForm, PublishTestForm

class RootView(View):
    def get(self, request):
        if User.objects.filter(is_superuser=True).exists():
            return redirect('/admin/')
        else:
            return redirect('/setup/')

class SetupWizardView(View):
    def get(self, request):
        if User.objects.filter(is_superuser=True).exists():
            return redirect('/admin/')
        form = SetupForm()
        return render(request, 'setup/wizard.html', {'form': form})

    def post(self, request):
        if User.objects.filter(is_superuser=True).exists():
            return redirect('/admin/')
        
        form = SetupForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['admin_username']
            password = form.cleaned_data['admin_password']
            token = form.cleaned_data['source_token']

            # Create superuser
            User.objects.create_superuser(username=username, password=password, email='')

            # Create Source
            Source.objects.create(name="Default Source", key=token)

            return redirect('/admin/login/')
        
        return render(request, 'setup/wizard.html', {'form': form})

class TestPublishView(LoginRequiredMixin, View):
    def get(self, request):
        form = PublishTestForm()
        return render(request, 'setup/test.html', {'form': form})

    def post(self, request):
        form = PublishTestForm(request.POST)
        task_id = None
        error = None
        
        if form.is_valid():
            source = form.cleaned_data['source']
            content_type = form.cleaned_data['content_type']
            path = form.cleaned_data['path']
            
            try:
                body = {
                    "type": content_type.source_code,
                    "path": path,
                }

                url = request.build_absolute_uri('/publish/')
                
                headers = {
                    'Authorization': f'Token {source.key}',
                    'Content-Type': 'application/json'
                }
                
                response = requests.post(url, json=body, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    task_id = data.get('task')
                else:
                    error = f"Error {response.status_code}: {response.text}"
                    
            except json.JSONDecodeError:
                error = "Invalid JSON payload"
            except Exception as e:
                error = str(e)
                
        return render(request, 'setup/test.html', {'form': form, 'task_id': task_id, 'error': error})
