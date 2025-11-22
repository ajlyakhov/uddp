from django import forms
from reference.models import Source, SourceContentMap

class SetupForm(forms.Form):
    admin_username = forms.CharField(max_length=150, initial="admin", help_text="Username for the administrator account")
    admin_password = forms.CharField(widget=forms.PasswordInput, initial="password", help_text="Password for the administrator account")
    source_token = forms.CharField(max_length=512, help_text="Authentication token for the source system")

class PublishTestForm(forms.Form):
    source = forms.ModelChoiceField(queryset=Source.objects.all(), empty_label="Select Source System")
    content_type = forms.CharField(max_length=100, help_text="Content type code (e.g., 'article', 'video')")
    payload = forms.CharField(widget=forms.Textarea, help_text="JSON payload for the publish request")
