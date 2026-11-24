from .models import MainPage

def base_template_data(request):
    """
    Provides global site data for base.html
    """
    return {
        'site': MainPage.objects.first()
    }