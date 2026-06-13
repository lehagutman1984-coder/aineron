from allauth.socialaccount.providers.vk.views import VKOAuth2Adapter
from allauth.socialaccount.providers.vk.provider import VKProvider
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
import requests

class CustomVKOAuth2Adapter(VKOAuth2Adapter):
    authorize_url = 'https://id.vk.ru/authorize'
    access_token_url = 'https://id.vk.ru/access_token'
    supports_pkce = True

    def complete_login(self, request, app, token, **kwargs):
        # Получаем данные пользователя через новый API VK
        headers = {'Authorization': f'Bearer {token.token}'}
        resp = requests.get('https://api.vk.com/method/users.get', 
                           params={
                               'v': '5.131',
                               'fields': 'email,first_name,last_name,photo_max'
                           },
                           headers=headers)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get('error'):
            raise Exception(f"VK API error: {data['error']}")
        
        user_data = data['response'][0]
        # Добавляем email, если он есть в ответе токена
        if hasattr(token, 'email') and token.email:
            user_data['email'] = token.email
        
        login = self.get_provider().sociallogin_from_response(request, user_data)
        return login
