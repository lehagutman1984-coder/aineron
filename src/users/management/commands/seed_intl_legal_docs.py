# -*- coding: utf-8 -*-
"""
Заполняет английские юр-документы (title_en/content_en) для aineron.net.

В отличие от setup_legal_documents (оферта самозанятого Иващенко А.А. для
aineron.ru — российские банковские реквизиты, Robokassa, законодательство РФ),
здесь — независимый текст для международного инстанса: оплата только
криптовалютой (Crypto Pay/@CryptoBot), без персональных данных исполнителя,
без привязки к конкретной юрисдикции.

Запуск (на сервере aineron.net): python manage.py seed_intl_legal_docs
По умолчанию не трогает уже заполненные *_en поля (чтобы не затереть правки
через админку). Полная перезапись: --force.
"""
from django.core.management.base import BaseCommand

from users.models import LegalDocument, SiteSettings

SUPPORT_EMAIL = "support@aineron.net"

TERMS_TITLE_EN = "Terms of Service"

TERMS_HTML_EN = """
<h2>1. About These Terms</h2>
<p>These Terms of Service ("Terms") govern your access to and use of aineron.net (the "Service"), a platform that provides access to third-party AI models for text chat, image and video generation, and related developer tools (API access). By creating an account, topping up your balance, or otherwise using the Service, you accept these Terms in full.</p>

<h2>2. Eligibility</h2>
<p>You must be at least 18 years old, or the age of legal majority in your jurisdiction, to use the Service. By using the Service you represent that you meet this requirement.</p>

<h2>3. The Service</h2>
<p>The Service gives you access to third-party large language models, image-generation models, and video-generation models through a unified chat interface, comparison tools, an OpenAI-compatible API, and related features published on the site. Features and available models may change over time.</p>

<h2>4. Credits, Payment &amp; Billing</h2>
<p>4.1. Access to paid usage is provided through a prepaid credit balance. You add credits to your account by paying with cryptocurrency (currently via Crypto Pay / @CryptoBot, in USDT/TON or other supported assets). We do not process bank cards and do not offer subscription-style recurring billing on this instance.</p>
<p>4.2. Each request to a paid model deducts credits from your balance at the price shown on the site at the time of the request. Prices may change; changes apply to future usage, not to credits already granted.</p>
<p>4.3. Credits do not expire and do not carry a cash value outside the Service — they may only be spent on usage of the Service.</p>
<p>4.4. If a generation request fails due to a technical error on our side or on the side of an underlying model provider, the credits reserved for that request are automatically refunded to your balance.</p>
<p>4.5. Because payments are made in cryptocurrency and are generally irreversible on the underlying blockchain, we do not offer cash refunds of a completed crypto payment except where required by law or at our sole discretion in cases of a genuine billing error. If you believe you were charged incorrectly, contact us at {support_email}.</p>

<h2>5. Acceptable Use</h2>
<p>You agree not to use the Service to:</p>
<ul>
<li>generate or distribute content that is illegal in your jurisdiction, including content that sexually exploits minors;</li>
<li>generate content that infringes the intellectual property, privacy, or other rights of third parties;</li>
<li>harass, defame, or impersonate any person, or generate non-consensual intimate imagery of real people;</li>
<li>attempt to reverse-engineer, decompile, scrape, or gain unauthorized access to the Service or its underlying infrastructure;</li>
<li>resell or sublicense API access issued to your account without our authorization;</li>
<li>use the Service to send spam or to abuse, overload, or disrupt the Service or its providers.</li>
</ul>
<p>We may suspend or terminate accounts that violate this section, with or without prior notice, and without a refund of unused credits obtained through abusive or fraudulent use.</p>

<h2>6. Intellectual Property &amp; Generated Content</h2>
<p>6.1. The Service, its software, and its branding are owned by the operator of aineron.net. You may not copy, modify, or create derivative works of the Service's software except as expressly permitted.</p>
<p>6.2. Subject to your compliance with these Terms and any applicable third-party model provider policies, you own the output generated in response to your own prompts and may use it for any lawful purpose. You are responsible for verifying that your intended use of generated content complies with applicable law and does not infringe third-party rights.</p>
<p>6.3. Content is produced automatically by artificial-intelligence systems. It may be inaccurate, incomplete, or unsuitable for a particular purpose, and does not constitute professional advice (legal, medical, financial, or otherwise). You are solely responsible for reviewing and validating any output before relying on it.</p>

<h2>7. Third-Party Services</h2>
<p>The Service relies on third-party AI model providers to process your requests and on a third-party payment processor (Crypto Pay / @CryptoBot) to process cryptocurrency payments. We are not responsible for the availability, accuracy, or errors of these third parties, though we will make reasonable efforts to route around outages where possible.</p>

<h2>8. Disclaimer of Warranties</h2>
<p>The Service is provided "as is" and "as available," without warranties of any kind, whether express or implied, including any warranty of uninterrupted or error-free operation, merchantability, or fitness for a particular purpose.</p>

<h2>9. Limitation of Liability</h2>
<p>To the maximum extent permitted by applicable law, the operator of the Service shall not be liable for any indirect, incidental, or consequential damages arising from your use of, or inability to use, the Service, including damages arising from outages of payment systems, internet providers, or third-party AI model providers. Nothing in these Terms limits any liability that cannot be limited under mandatory law.</p>

<h2>10. Suspension &amp; Termination</h2>
<p>We may suspend or terminate your account for violation of these Terms or applicable law. Where practical, we will notify you by email. You may stop using the Service and request deletion of your account at any time by contacting {support_email}.</p>

<h2>11. Changes to These Terms</h2>
<p>We may update these Terms from time to time. The updated version takes effect once posted on the site. Continued use of the Service after an update constitutes acceptance of the revised Terms.</p>

<h2>12. Governing Law</h2>
<p>These Terms do not limit any non-waivable statutory rights you may have under the mandatory consumer-protection laws of your country of residence. Disputes should first be raised with us at {support_email} so we can attempt to resolve them informally.</p>

<h2>13. Contact</h2>
<p>Questions about these Terms can be sent to <strong>{support_email}</strong>.</p>
""".format(support_email=SUPPORT_EMAIL)

PRIVACY_TITLE_EN = "Privacy Policy"

PRIVACY_HTML_EN = """
<h2>1. Overview</h2>
<p>This Privacy Policy explains what data aineron.net (the "Service") collects, why, and how it is used. By using the Service, you agree to the practices described here.</p>

<h2>2. Data We Collect</h2>
<ul>
<li><strong>Account data:</strong> the email address (or the identifier and public profile data from a third-party sign-in provider, if you use one) you use to register.</li>
<li><strong>Payment data:</strong> a cryptocurrency payment reference/invoice ID confirming a top-up. Payments are processed by a third-party processor (Crypto Pay / @CryptoBot); we do not collect or store your wallet private keys or bank card details.</li>
<li><strong>Usage &amp; content data:</strong> the prompts, files, and other content you submit to the Service, and the outputs generated in response, to the extent necessary to provide the requested functionality.</li>
<li><strong>Technical data:</strong> IP address, browser type, device information, and access timestamps, used for security, abuse prevention, and basic service diagnostics.</li>
<li><strong>Support data:</strong> the contents of any message you send us for support purposes.</li>
</ul>

<h2>3. How We Use Data</h2>
<p>We use the data described above to operate and maintain the Service, process your requests to third-party AI model providers, process payments, prevent fraud and abuse, and respond to support requests. We do not sell your personal data.</p>

<h2>4. Third-Party Processors</h2>
<p>To provide the Service, certain data is shared with:</p>
<ul>
<li>third-party AI model providers, to the extent necessary to process your prompts and return a result;</li>
<li>our cryptocurrency payment processor (Crypto Pay / @CryptoBot), to confirm and process top-ups;</li>
<li>our hosting/infrastructure providers, to store and operate the Service.</li>
</ul>
<p>We disclose data to government authorities only where legally required to do so.</p>

<h2>5. Cookies</h2>
<p>The Service uses essential cookies/local storage required for authentication and basic functionality (for example, keeping you signed in and remembering your interface preferences). You can control cookies through your browser settings, though disabling essential cookies may prevent parts of the Service from working correctly.</p>

<h2>6. Data Retention</h2>
<p>We retain your data for as long as your account is active or as needed to provide the Service. If you request account deletion, we will delete or anonymize your personal data within a reasonable period, except where we are required to retain certain records by law or for legitimate security purposes.</p>

<h2>7. Your Rights</h2>
<p>Depending on your jurisdiction, you may have the right to access, correct, or request deletion of your personal data. To exercise these rights, contact us at <strong>{support_email}</strong>.</p>

<h2>8. Children's Privacy</h2>
<p>The Service is not directed to individuals under 18 years of age (or the age of legal majority in their jurisdiction), and we do not knowingly collect personal data from them.</p>

<h2>9. Security</h2>
<p>We take reasonable technical and organizational measures to protect your data, but no method of transmission or storage is completely secure, and we cannot guarantee absolute security.</p>

<h2>10. International Data</h2>
<p>Your data may be processed and stored in countries other than your own, including wherever our hosting providers and third-party AI model providers operate their infrastructure.</p>

<h2>11. Changes to This Policy</h2>
<p>We may update this Privacy Policy from time to time. The updated version takes effect once posted on the site.</p>

<h2>12. Contact</h2>
<p>Questions about this Privacy Policy can be sent to <strong>{support_email}</strong>.</p>
""".format(support_email=SUPPORT_EMAIL)


class Command(BaseCommand):
    help = "Заполняет английские Terms of Service / Privacy Policy для aineron.net (без данных исполнителя, крипта-оплата)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true",
            help="Перезаписать *_en поля, даже если они уже заполнены",
        )

    def handle(self, *args, **options):
        force = options["force"]
        docs = [
            ("terms", TERMS_TITLE_EN, TERMS_HTML_EN),
            ("privacy", PRIVACY_TITLE_EN, PRIVACY_HTML_EN),
        ]
        for doc_type, title_en, content_en in docs:
            obj = LegalDocument.objects.filter(document_type=doc_type).first()
            if obj is None:
                obj = LegalDocument.objects.create(
                    document_type=doc_type, title=title_en, content=content_en.strip(),
                    title_en=title_en, content_en=content_en.strip(),
                )
                self.stdout.write(self.style.SUCCESS(f"{doc_type}: created"))
                continue

            is_empty = not (obj.content_en or "").strip()
            if force or is_empty:
                obj.title_en = title_en
                obj.content_en = content_en.strip()
                obj.save(update_fields=["title_en", "content_en"])
                self.stdout.write(self.style.SUCCESS(f"{doc_type}: en content updated"))
            else:
                self.stdout.write(f"{doc_type}: en content already set, skipped (use --force to overwrite)")

        settings_obj = SiteSettings.get_settings()
        if force or not settings_obj.support_email or "example.com" in settings_obj.support_email:
            settings_obj.support_email = SUPPORT_EMAIL
            settings_obj.save(update_fields=["support_email"])
            self.stdout.write(self.style.SUCCESS(f"support_email set to {SUPPORT_EMAIL}"))
        else:
            self.stdout.write(f"support_email already set to {settings_obj.support_email}, left unchanged")
