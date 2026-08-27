"""
Email Service for btpAO SaaS Platform.
Handles transactional emails (Password Reset, Team Invitations) with high-end branded HTML templates.
Zero generic text emails — 100% styled to look like official btpAO platform communications.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional
import logging

logger = logging.getLogger("btpao.email")

# In-memory store of recent transactional emails for audit and development verification
RECENT_SENT_EMAILS: List[Dict[str, str]] = []


def build_password_reset_html(to_email: str, reset_url: str, user_name: Optional[str] = None) -> str:
    """Generates a responsive, ultra-premium B2B BTP branded HTML email template."""
    display_name = user_name or to_email.split('@')[0]
    
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Réinitialisation de votre mot de passe btpAO</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #090d16;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #e2e8f0;
    }}
    .container {{
      max-width: 600px;
      margin: 40px auto;
      background-color: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 20px;
      overflow: hidden;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
    }}
    .header {{
      background: linear-gradient(135deg, #0284c7 0%, #0369a1 50%, #0f172a 100%);
      padding: 36px 32px 30px;
      text-align: center;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }}
    .logo-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid rgba(56, 189, 248, 0.4);
      padding: 8px 18px;
      border-radius: 9999px;
      margin-bottom: 16px;
    }}
    .logo-text {{
      font-size: 20px;
      font-weight: 900;
      letter-spacing: -0.5px;
      color: #ffffff;
    }}
    .logo-accent {{
      color: #38bdf8;
    }}
    .header h1 {{
      margin: 0;
      font-size: 22px;
      font-weight: 800;
      color: #ffffff;
      letter-spacing: -0.3px;
    }}
    .header p {{
      margin: 8px 0 0;
      font-size: 13px;
      color: #bae6fd;
    }}
    .content {{
      padding: 36px 32px;
    }}
    .greeting {{
      font-size: 15px;
      font-weight: 600;
      color: #f8fafc;
      margin-bottom: 16px;
    }}
    .message {{
      font-size: 14px;
      line-height: 1.6;
      color: #94a3b8;
      margin-bottom: 28px;
    }}
    .btn-container {{
      text-align: center;
      margin: 32px 0;
    }}
    .btn {{
      display: inline-block;
      background: linear-gradient(135deg, #0284c7 0%, #0ea5e9 100%);
      color: #ffffff !important;
      font-size: 14px;
      font-weight: 700;
      text-decoration: none;
      padding: 14px 32px;
      border-radius: 12px;
      box-shadow: 0 10px 25px -5px rgba(2, 132, 199, 0.4);
      transition: all 0.2s ease;
    }}
    .alert-box {{
      background-color: #1e293b;
      border-left: 4px solid #38bdf8;
      border-radius: 8px;
      padding: 14px 18px;
      margin: 24px 0;
      font-size: 12px;
      line-height: 1.5;
      color: #cbd5e1;
    }}
    .link-fallback {{
      background-color: #0b1120;
      border: 1px solid #1e293b;
      border-radius: 8px;
      padding: 12px;
      font-family: monospace;
      font-size: 11px;
      color: #38bdf8;
      word-break: break-all;
      margin-top: 10px;
    }}
    .security-notice {{
      font-size: 12px;
      color: #64748b;
      line-height: 1.5;
      margin-top: 24px;
      padding-top: 20px;
      border-top: 1px solid #1e293b;
    }}
    .footer {{
      background-color: #0b1120;
      padding: 24px 32px;
      text-align: center;
      border-top: 1px solid #1e293b;
      font-size: 11px;
      color: #475569;
      line-height: 1.6;
    }}
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <div class="header">
      <div class="logo-badge">
        <span class="logo-text">btp<span class="logo-accent">AO</span></span>
      </div>
      <h1>Réinitialisation de mot de passe</h1>
      <p>Sécurité & gestion des accès à votre espace entreprise</p>
    </div>

    <!-- Content -->
    <div class="content">
      <div class="greeting">Bonjour {display_name},</div>
      
      <div class="message">
        Une demande de réinitialisation de mot de passe a été initiée pour votre compte entreprise <strong>{to_email}</strong> sur la plateforme btpAO.
      </div>

      <div class="btn-container">
        <a href="{reset_url}" class="btn" target="_blank">
          Définir un nouveau mot de passe &rarr;
        </a>
      </div>

      <div class="alert-box">
        <strong>⏱️ Sécurité du lien :</strong> Ce lien sécurisé est valable pendant <strong>1 heure</strong> et ne peut être utilisé qu'une seule fois.
      </div>

      <div style="font-size: 12px; color: #64748b; margin-top: 20px;">
        Si le bouton ne s'affiche pas correctement, copiez et collez l'adresse suivante dans votre navigateur :
      </div>
      <div class="link-fallback">
        {reset_url}
      </div>

      <div class="security-notice">
        <strong>Vous n'avez pas demandé cette réinitialisation ?</strong><br>
        Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet e-mail en toute tranquillité. Votre mot de passe actuel reste actif et inchangé.
      </div>
    </div>

    <!-- Footer -->
    <div class="footer">
      <strong>btpAO</strong> &bull; Plateforme SaaS B2B de réponse aux Appels d'Offres BTP<br>
      Extraction DCE automatique &bull; Rédaction de mémoires techniques IA &bull; Chiffrage &bull; Conformité marchés publics<br>
      <em>Cet e-mail a été envoyé automatiquement par le service de sécurité btpAO. Ne pas répondre directement.</em>
    </div>
  </div>
</body>
</html>"""
    return html


def send_password_reset_email(
    to_email: str,
    reset_url: str,
    user_name: Optional[str] = None
) -> bool:
    """
    Sends the password reset email to the recipient.
    Uses configured SMTP credentials from environment if available,
    or stores/logs in development mode.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL", "securite@btpao.fr")
    from_name = os.getenv("SMTP_FROM_NAME", "btpAO Sécurité")

    html_content = build_password_reset_html(to_email=to_email, reset_url=reset_url, user_name=user_name)

    # In-memory logging for audit, debugging, and verification
    RECENT_SENT_EMAILS.append({
        "to_email": to_email,
        "subject": "[btpAO] Réinitialisation de votre mot de passe",
        "reset_url": reset_url,
        "from_email": f"{from_name} <{from_email}>",
    })

    if smtp_host and smtp_user and smtp_password:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "[btpAO] Réinitialisation de votre mot de passe"
            msg["From"] = f"{from_name} <{from_email}>"
            msg["To"] = to_email

            text_content = (
                f"Bonjour,\n\n"
                f"Pour réinitialiser votre mot de passe btpAO, rendez-vous sur le lien suivant :\n"
                f"{reset_url}\n\n"
                f"Ce lien est valable 1 heure.\n"
                f"L'équipe btpAO"
            )
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            if smtp_port == 465:
                with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as server:
                    server.login(smtp_user, smtp_password)
                    server.sendmail(from_email, [to_email], msg.as_string())
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                    server.sendmail(from_email, [to_email], msg.as_string())

            logger.info(f"Password reset email sent to {to_email} via SMTP ({smtp_host}).")
            return True
        except Exception as e:
            logger.error(f"Failed to send email via SMTP to {to_email}: {e}")
            return False

    # Development / Fallback mode
    logger.info(
        f"[DEV EMAIL] Password reset email for {to_email} generated successfully.\n"
        f"Reset URL: {reset_url}"
    )
    return True


def build_team_invitation_html(
    to_email: str,
    invitation_url: str,
    tenant_name: str,
    role_label: str,
    invited_by_name: Optional[str] = None,
) -> str:
    """Generates an ultra-premium branded HTML email for team member invitations."""
    inviter = invited_by_name or "Un administrateur de votre entreprise"

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Invitation à rejoindre l'espace entreprise btpAO</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #090d16;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #e2e8f0;
    }}
    .container {{
      max-width: 600px;
      margin: 40px auto;
      background-color: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 20px;
      overflow: hidden;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
    }}
    .header {{
      background: linear-gradient(135deg, #0284c7 0%, #0369a1 50%, #0f172a 100%);
      padding: 36px 32px 30px;
      text-align: center;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }}
    .logo-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid rgba(56, 189, 248, 0.4);
      padding: 8px 18px;
      border-radius: 9999px;
      margin-bottom: 16px;
    }}
    .logo-text {{
      font-size: 20px;
      font-weight: 900;
      letter-spacing: -0.5px;
      color: #ffffff;
    }}
    .logo-accent {{
      color: #38bdf8;
    }}
    .header h1 {{
      margin: 0;
      font-size: 22px;
      font-weight: 800;
      color: #ffffff;
      letter-spacing: -0.3px;
    }}
    .header p {{
      margin: 8px 0 0;
      font-size: 13px;
      color: #bae6fd;
    }}
    .content {{
      padding: 36px 32px;
    }}
    .greeting {{
      font-size: 15px;
      font-weight: 600;
      color: #f8fafc;
      margin-bottom: 16px;
    }}
    .message {{
      font-size: 14px;
      line-height: 1.6;
      color: #94a3b8;
      margin-bottom: 24px;
    }}
    .role-badge-box {{
      background-color: #1e293b;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 16px 20px;
      margin: 20px 0;
    }}
    .role-badge-title {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #64748b;
      margin-bottom: 4px;
    }}
    .role-badge-val {{
      font-size: 16px;
      font-weight: 700;
      color: #38bdf8;
    }}
    .btn-container {{
      text-align: center;
      margin: 32px 0;
    }}
    .btn {{
      display: inline-block;
      background: linear-gradient(135deg, #0284c7 0%, #0ea5e9 100%);
      color: #ffffff !important;
      font-size: 14px;
      font-weight: 700;
      text-decoration: none;
      padding: 14px 32px;
      border-radius: 12px;
      box-shadow: 0 10px 25px -5px rgba(2, 132, 199, 0.4);
      transition: all 0.2s ease;
    }}
    .alert-box {{
      background-color: #1e293b;
      border-left: 4px solid #38bdf8;
      border-radius: 8px;
      padding: 14px 18px;
      margin: 24px 0;
      font-size: 12px;
      line-height: 1.5;
      color: #cbd5e1;
    }}
    .link-fallback {{
      background-color: #0b1120;
      border: 1px solid #1e293b;
      border-radius: 8px;
      padding: 12px;
      font-family: monospace;
      font-size: 11px;
      color: #38bdf8;
      word-break: break-all;
      margin-top: 10px;
    }}
    .footer {{
      background-color: #0b1120;
      padding: 24px 32px;
      text-align: center;
      border-top: 1px solid #1e293b;
      font-size: 11px;
      color: #475569;
      line-height: 1.6;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="logo-badge">
        <span class="logo-text">btp<span class="logo-accent">AO</span></span>
      </div>
      <h1>Invitation à rejoindre l'équipe</h1>
      <p>Accès collaboratif aux dossiers d'Appels d'Offres</p>
    </div>

    <div class="content">
      <div class="greeting">Bonjour,</div>
      
      <div class="message">
        <strong>{inviter}</strong> vous invite à rejoindre l'espace entreprise <strong>{tenant_name}</strong> sur la plateforme btpAO.
      </div>

      <div class="role-badge-box">
        <div class="role-badge-title">Rôle attribué sur la plateforme</div>
        <div class="role-badge-val">{role_label}</div>
      </div>

      <div class="message">
        Ce rôle vous permet de collaborer sur la préparation des dossiers, la rédaction des mémoires techniques assistée par IA et le suivi des marchés publics.
      </div>

      <div class="btn-container">
        <a href="{invitation_url}" class="btn" target="_blank">
          Accepter l'invitation &rarr;
        </a>
      </div>

      <div class="alert-box">
        <strong>⏱️ Validité :</strong> Cette invitation est valable pendant <strong>7 jours</strong>.
      </div>

      <div style="font-size: 12px; color: #64748b; margin-top: 20px;">
        Si le bouton ne s'affiche pas correctement, rendez-vous à l'adresse suivante :
      </div>
      <div class="link-fallback">
        {invitation_url}
      </div>
    </div>

    <div class="footer">
      <strong>btpAO</strong> &bull; Plateforme SaaS B2B de réponse aux Appels d'Offres BTP<br>
      <em>Cet e-mail d'invitation a été émis automatiquement. Ne pas répondre directement.</em>
    </div>
  </div>
</body>
</html>"""
    return html


def send_team_invitation_email(
    to_email: str,
    invitation_url: str,
    tenant_name: str,
    role: str,
    invited_by_name: Optional[str] = None,
) -> bool:
    """
    Sends the team invitation email to the recipient with branded HTML template.
    """
    role_labels = {
        "owner": "Chef d'Entreprise / Administrateur",
        "conducteur_travaux": "Conducteur de Travaux",
        "chiffreur": "Ingénieur Études & Chiffrage",
        "member": "Collaborateur",
        "read_only": "Observateur (Lecture seule)",
    }
    role_label = role_labels.get(role, role.replace('_', ' ').capitalize())

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL", "invitations@btpao.fr")
    from_name = os.getenv("SMTP_FROM_NAME", f"btpAO — {tenant_name}")

    html_content = build_team_invitation_html(
        to_email=to_email,
        invitation_url=invitation_url,
        tenant_name=tenant_name,
        role_label=role_label,
        invited_by_name=invited_by_name,
    )

    RECENT_SENT_EMAILS.append({
        "to_email": to_email,
        "subject": f"[btpAO] Invitation à rejoindre l'équipe {tenant_name}",
        "invitation_url": invitation_url,
        "role": role,
        "from_email": f"{from_name} <{from_email}>",
    })

    if smtp_host and smtp_user and smtp_password:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[btpAO] Invitation à rejoindre l'équipe {tenant_name}"
            msg["From"] = f"{from_name} <{from_email}>"
            msg["To"] = to_email

            text_content = (
                f"Bonjour,\n\n"
                f"Vous avez été invité(e) à rejoindre l'entreprise {tenant_name} sur btpAO avec le rôle {role_label}.\n\n"
                f"Pour accepter l'invitation, cliquez sur ce lien :\n"
                f"{invitation_url}\n\n"
                f"L'équipe btpAO"
            )
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            if smtp_port == 465:
                with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as server:
                    server.login(smtp_user, smtp_password)
                    server.sendmail(from_email, [to_email], msg.as_string())
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                    server.sendmail(from_email, [to_email], msg.as_string())

            logger.info(f"Team invitation email sent to {to_email} via SMTP ({smtp_host}).")
            return True
        except Exception as e:
            logger.error(f"Failed to send team invitation email via SMTP to {to_email}: {e}")
            return False

    logger.info(
        f"[DEV EMAIL] Team invitation email for {to_email} generated successfully.\n"
        f"Role: {role_label}\n"
        f"Invitation URL: {invitation_url}"
    )
    return True

