import os
import logging
import smtplib
import ssl
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from godata import database
from godata.repos import TripRepo, ParcelRepo

log = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Europe/Paris")


# ── Email helpers ────────────────────────────────────────────────────────────

def _smtp_cfg() -> dict:
    return {
        "host": os.environ.get("SMTP_HOST", ""),
        "port": int(os.environ.get("SMTP_PORT", 465)),
        "user": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASS", ""),
        "from": os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "")),
    }


def _send(to: str, subject: str, html: str) -> None:
    cfg = _smtp_cfg()
    if not cfg["host"] or not cfg["user"]:
        log.warning("SMTP non configuré — e-mail ignoré (destinataire: %s)", to)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))

    ctx = ssl.create_default_context()
    try:
        if cfg["port"] == 465:
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=ctx) as s:
                s.login(cfg["user"], cfg["password"])
                s.sendmail(cfg["from"], [to], msg.as_string())
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"]) as s:
                s.ehlo()
                s.starttls(context=ctx)
                s.login(cfg["user"], cfg["password"])
                s.sendmail(cfg["from"], [to], msg.as_string())
        log.info("E-mail envoyé à %s : %s", to, subject)
    except Exception:
        log.exception("Échec envoi e-mail à %s", to)


def _warning_html(trip) -> str:
    travel_date = trip.date.strftime("%d/%m/%Y") if hasattr(trip.date, "strftime") else trip.date
    return f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:24px">
      <div style="background:#0f5c32;border-radius:12px;padding:20px 24px;color:white;margin-bottom:24px">
        <strong style="font-size:20px">📦 JIBLI DZ</strong>
      </div>
      <h2 style="color:#111827">⚠️ Votre trajet expire demain</h2>
      <p style="color:#6b7280;line-height:1.6">
        Votre annonce de trajet <strong>{trip.from_city} → {trip.to_city}</strong>
        prévue le <strong>{travel_date}</strong> sera automatiquement supprimée demain soir.
      </p>
      <div style="background:#fde68a;border-radius:10px;padding:16px;margin:20px 0;color:#92400e">
        Si votre trajet est toujours d'actualité, supprimez et re-publiez votre annonce sur JIBLI DZ
        pour qu'elle reste visible.
      </div>
      <p style="color:#6b7280;font-size:13px;margin-top:32px">
        Cet e-mail a été envoyé automatiquement par JIBLI DZ · France ⇄ Algérie
      </p>
    </div>
    """


def _deleted_html(trip) -> str:
    travel_date = trip.date.strftime("%d/%m/%Y") if hasattr(trip.date, "strftime") else trip.date
    return f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:24px">
      <div style="background:#0f5c32;border-radius:12px;padding:20px 24px;color:white;margin-bottom:24px">
        <strong style="font-size:20px">📦 JIBLI DZ</strong>
      </div>
      <h2 style="color:#111827">🗑 Votre trajet a été supprimé</h2>
      <p style="color:#6b7280;line-height:1.6">
        Votre annonce de trajet <strong>{trip.from_city} → {trip.to_city}</strong>
        du <strong>{travel_date}</strong> a été automatiquement supprimée car la date est passée.
      </p>
      <p style="color:#6b7280;line-height:1.6">
        Vous pouvez re-publier une nouvelle annonce à tout moment sur JIBLI DZ.
      </p>
      <p style="color:#6b7280;font-size:13px;margin-top:32px">
        Cet e-mail a été envoyé automatiquement par JIBLI DZ · France ⇄ Algérie
      </p>
    </div>
    """


# ── Parcel-match notification ────────────────────────────────────────────────

def _match_html(trip, parcel) -> str:
    travel_date = trip.date.strftime("%d/%m/%Y") if hasattr(trip.date, "strftime") else trip.date
    return f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:24px">
      <div style="background:#0f5c32;border-radius:12px;padding:20px 24px;color:white;margin-bottom:24px">
        <strong style="font-size:20px">📦 JIBLI DZ</strong>
      </div>
      <h2 style="color:#111827">🎉 Un voyageur correspond à votre colis !</h2>
      <p style="color:#6b7280;line-height:1.6">
        Bonne nouvelle — un voyageur vient de publier un trajet
        <strong>{trip.from_city} → {trip.to_city}</strong>
        prévu le <strong>{travel_date}</strong>.
        Votre colis (<em>{parcel.description}</em>) pourrait lui être confié.
      </p>
      <div style="background:#d1fae5;border-radius:10px;padding:16px;margin:20px 0;color:#065f46">
        Contactez <strong>{trip.name}</strong> via WhatsApp pour vous mettre d'accord.
      </div>
      <p style="color:#6b7280;font-size:13px;margin-top:32px">
        Cet e-mail a été envoyé automatiquement par JIBLI DZ · France ⇄ Algérie
      </p>
    </div>
    """


def notify_matching_parcels(trip) -> None:
    """Called in background after a new trip is published."""
    try:
        database.connect(reuse_if_open=True)
        parcels = ParcelRepo.list_matching(trip.from_city, trip.to_city)
        log.info("notify_matching_parcels: %d colis pour %s→%s", len(parcels), trip.from_city, trip.to_city)
        for parcel in parcels:
            try:
                owner_email = parcel.owner.email
            except Exception:
                continue
            if owner_email:
                _send(
                    owner_email,
                    f"🎉 Un voyageur {trip.from_city} → {trip.to_city} cherche des colis !",
                    _match_html(trip, parcel),
                )
    except Exception:
        log.exception("Erreur notify_matching_parcels")
    finally:
        if not database.is_closed():
            database.close()


# ── Daily job ────────────────────────────────────────────────────────────────

def daily_trip_cleanup() -> None:
    log.info("== Nettoyage quotidien des trajets ==")
    database.connect(reuse_if_open=True)
    try:
        today = date.today()
        tomorrow = today + timedelta(days=1)

        # 1. Alert: trips expiring tomorrow
        expiring = TripRepo.list_expiring_on(tomorrow)
        log.info("%d trajet(s) expirent demain", len(expiring))
        for trip in expiring:
            try:
                owner_email = trip.owner.email if trip.owner_id else None
            except Exception:
                owner_email = None
            if owner_email:
                _send(
                    owner_email,
                    f"⚠️ Votre trajet {trip.from_city} → {trip.to_city} expire demain",
                    _warning_html(trip),
                )

        # 2. Delete: trips whose date is strictly before today
        expired = TripRepo.pop_expired(today)
        log.info("%d trajet(s) supprimé(s) (date passée)", len(expired))
        for trip in expired:
            log.info("  Suppression trajet #%s %s→%s le %s", trip.id, trip.from_city, trip.to_city, trip.date)
            try:
                owner_email = trip.owner.email if trip.owner_id else None
            except Exception:
                owner_email = None
            if owner_email:
                _send(
                    owner_email,
                    f"🗑 Votre trajet {trip.from_city} → {trip.to_city} a été supprimé",
                    _deleted_html(trip),
                )

    except Exception:
        log.exception("Erreur lors du nettoyage quotidien")
    finally:
        if not database.is_closed():
            database.close()


def start_scheduler() -> None:
    # Run every day at 08:00 Paris time
    scheduler.add_job(daily_trip_cleanup, "cron", hour=8, minute=0, id="trip_cleanup", replace_existing=True)
    scheduler.start()
    log.info("Scheduler démarré — nettoyage quotidien à 08h00 (Europe/Paris)")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
