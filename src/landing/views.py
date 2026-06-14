from django.shortcuts import render


def custom_404_view(request, exception):
    return render(request, 'neuro/404.html', status=404)


def api_docs(request):
    return render(request, 'neuro/api_docs.html')


def ide_integrations(request):
    return render(request, 'neuro/ide_integrations.html')
