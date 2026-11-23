"""Help & Support: answers to common questions and a way to contact the team.

Messages sent here land in the admin Inquiries inbox, the same as the About page form.
"""
from django.contrib import messages
from django.shortcuts import redirect, render

from ..forms import ContactForm

# (question, answer) shown to everyone.
USER_FAQ = [
    ("How do I add a plant?",
     "Open My Plants and choose Add Plant. Pick its species from the library and the care plan, "
     "watering reminders and schedule are set up for you."),
    ("How do watering reminders work?",
     "Each reminder repeats on the interval you set. Mark it as watered and the next date moves forward "
     "automatically. You can pause a reminder at any time."),
    ("What does a health check do?",
     "Upload a photo of the plant or a leaf. You can name the problem yourself or let Plant Care look for it, "
     "then follow the treatment steps and track progress until it is resolved."),
    ("Can I change when reminders arrive?",
     "Yes. In Settings, open Care Preferences to set your default reminder time and watering method, "
     "and Notifications to choose which alerts you get."),
    ("How do I download or delete my data?",
     "Settings has a Privacy & Data tab where you can export everything as a file or delete your account."),
]

# Shown to admins instead.
ADMIN_FAQ = [
    ("How do I approve a new account?",
     "New accounts start as Pending. The Admin Dashboard lists them under Pending Approval; choose Activate."),
    ("Where do contact messages go?",
     "Messages from the About page and from the Help page appear in Inquiries, linked from the Admin "
     "Dashboard. Reply by email, then mark them as handled."),
    ("How do I add a species to the Plant Library?",
     "Open Species and choose Add Species. Add a photo so it looks good on the public Plant Library."),
    ("What does Care History show?",
     "Care activity logged by every user. Filter by user, activity or period, or search plant names and notes."),
]


def index(request):
    user = request.user
    if request.method == "POST" and not user.is_staff:
        # Name and email come from the account, not the form.
        data = request.POST.copy()
        data["name"] = user.full_name or user.email
        data["email"] = user.email
        form = ContactForm(data)
        if form.is_valid():
            form.save()
            messages.success(request, f"Thanks! Your message was sent. We'll reply to {user.email}.")
            return redirect("help")
    else:
        form = ContactForm()

    return render(request, "help/index.html", {
        "faq": ADMIN_FAQ if user.is_staff else USER_FAQ,
        "form": form,
    })
