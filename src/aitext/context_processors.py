from .models import NeuralNetwork

def footer_networks(request):
    return {
        'direct_networks': NeuralNetwork.objects.filter(is_active=True, is_direct=True).order_by('order')[:20],
        'custom_networks': NeuralNetwork.objects.filter(is_active=True, is_custom=True).order_by('order')[:20],
    }