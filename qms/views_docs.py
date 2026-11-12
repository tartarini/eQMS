from datetime import date

from django.contrib import messages
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import doc_exchange, services
from . import workflow as wf

from .access import current_device, form_page, qms_member, require_access, run, scope
from .forms import (DocumentForm, DocumentImportForm, SignForm, TrainingRequirementForm,
                    VersionForm)
from .models import (AuditEvent, Document, DocumentVersion, Signature, TrainingAssignment,
                     TrainingRequirement)
from .services import TransitionError


@qms_member
def document_list(request):
    show = request.GET.get("show", "current")
    docs = Document.objects.select_related("owner", "device").prefetch_related("versions")
    docs = scope(docs, request, allow_shared=True)
    if show == "current":
        docs = docs.filter(obsolete=False)
    return render(request, "qms/document_list.html", {"documents": docs, "show": show})


@qms_member
def document_create(request):
    form = DocumentForm(request.POST or None, user=request.user,
                        initial={"device": current_device(request)})
    if request.method == "POST" and form.is_valid():
        doc = form.save()
        messages.success(request, f"{doc.number} created. Add its first version.")
        return redirect("qms:document_detail", number=doc.number)
    return form_page(request, form, "New controlled document", reverse("qms:document_list"))


@qms_member
def document_edit(request, number):
    doc = get_object_or_404(Document, number=number)
    require_access(request, doc.device)
    form = DocumentForm(request.POST or None, instance=doc, user=request.user)
    if request.method == "POST" and form.is_valid():
        if run(request, form.save, success="Saved."):
            return redirect("qms:document_detail", number=number)
    return form_page(request, form, f"Edit {doc.number}",
                     reverse("qms:document_detail", args=[number]))


@qms_member
def document_detail(request, number):
    doc = get_object_or_404(Document.objects.select_related("owner"), number=number)
    require_access(request, doc.device)
    versions = list(doc.versions.select_related("author", "change_request"))
    sigs = Signature.objects.filter(object_type="Document Version",
                                    object_ref__in=[v.audit_ref for v in versions]) | \
        Signature.for_object(doc)
    events = AuditEvent.objects.filter(
        object_ref__in=[doc.audit_ref] + [v.audit_ref for v in versions]).order_by("-id")
    return render(request, "qms/document_detail.html", {
        "doc": doc, "versions": versions, "open_version": doc.open_version,
        "effective": doc.effective_version, "sign_form": SignForm(),
        "requirements": doc.training_requirements.select_related("group").filter(active=True),
        "req_form": TrainingRequirementForm(),
        "signatures": sigs.order_by("signed_at"), "events": events,
        "is_qa": services.user_has_role(request.user, [wf.QA], doc.device),
        "next_major": doc.suggest_next_version(major=True),
        "next_minor": doc.suggest_next_version(major=False),
    })


@qms_member
def version_create(request, number):
    doc = get_object_or_404(Document, number=number)
    require_access(request, doc.device)
    initial = {"version": doc.suggest_next_version(major=True)}
    form = VersionForm(request.POST or None, request.FILES or None, initial=initial,
                       user=request.user)
    if request.method == "POST" and form.is_valid():
        v = run(request, services.create_version, doc, request.user,
                version=form.cleaned_data["version"],
                change_summary=form.cleaned_data["change_summary"],
                file=form.cleaned_data.get("file"),
                change_request=form.cleaned_data.get("change_request"),
                success="Draft created.")
        if v:
            return redirect("qms:document_detail", number=number)
    return form_page(request, form, f"New version of {doc.number}",
                     reverse("qms:document_detail", args=[number]),
                     intro="Upload the document and summarise what changed. It stays a draft "
                           "until you submit it for review.")


@qms_member
def version_edit(request, pk):
    v = get_object_or_404(DocumentVersion, pk=pk)
    require_access(request, v.document.device)
    if not v.is_editable:
        messages.error(request, f"{v} is {v.get_status_display().lower()} and frozen.")
        return redirect("qms:document_detail", number=v.document.number)
    form = VersionForm(request.POST or None, request.FILES or None, instance=v,
                       user=request.user)
    if request.method == "POST" and form.is_valid():
        if run(request, form.save, success="Draft updated."):
            return redirect("qms:document_detail", number=v.document.number)
    return form_page(request, form, f"Edit draft {v}",
                     reverse("qms:document_detail", args=[v.document.number]))


@qms_member
@require_POST
def version_action(request, pk, action):
    v = get_object_or_404(DocumentVersion, pk=pk)
    require_access(request, v.document.device)
    form = SignForm(request.POST)
    form.is_valid()
    comment = form.cleaned_data.get("comment", "")
    secret = form.cleaned_data.get("password", "")
    u = request.user
    actions = {
        "submit": (lambda: services.submit_version(v, u), "Submitted for review."),
        "return": (lambda: services.return_version(v, u, comment), "Returned to draft."),
        "approve": (lambda: services.approve_version(v, u, secret, comment), "Approved and signed."),
        "effective": (lambda: services.make_effective(v, u),
                      "Now effective. Training has been assigned."),
        "review": (lambda: services.review_no_change(v, u, secret, comment),
                   "Periodic review recorded."),
    }
    if action not in actions:
        messages.error(request, "Unknown action.")
    else:
        func, msg = actions[action]
        run(request, func, success=msg)
    return redirect("qms:document_detail", number=v.document.number)


@qms_member
@require_POST
def document_obsolete(request, number):
    doc = get_object_or_404(Document, number=number)
    require_access(request, doc.device)
    form = SignForm(request.POST)
    form.is_valid()
    run(request, services.obsolete_document, doc, request.user,
        form.cleaned_data.get("password", ""), form.cleaned_data.get("comment", ""),
        success=f"{doc.number} withdrawn.")
    return redirect("qms:document_detail", number=number)


@qms_member
def version_download(request, pk):
    v = get_object_or_404(DocumentVersion, pk=pk)
    require_access(request, v.document.device)
    if not v.file:
        messages.error(request, "No file uploaded yet.")
        return redirect("qms:document_detail", number=v.document.number)
    if not v.verify():
        messages.error(request, f"Integrity check failed for {v}: the stored file does not "
                                "match its recorded checksum.")
        return redirect("qms:document_detail", number=v.document.number)
    return FileResponse(v.file.open("rb"), as_attachment=True,
                        filename=f"{v.document.number}_v{v.version}_{v.original_name}")


@qms_member
@require_POST
def requirement_add(request, number):
    doc = get_object_or_404(Document, number=number)
    require_access(request, doc.device)
    if not services.user_has_role(request.user, [wf.QA], doc.device):
        messages.error(request, "Requires role: QA.")
        return redirect("qms:document_detail", number=number)
    form = TrainingRequirementForm(request.POST)
    if form.is_valid():
        req, created = TrainingRequirement.objects.get_or_create(
            document=doc, group=form.cleaned_data["group"])
        if not created and not req.active:
            req.active = True
            req.save()
        assigned = services.sync_training()
        messages.success(request, f"{form.cleaned_data['group'].name} must now be trained on "
                                  f"{doc.number}. {len(assigned)} assignment(s) created.")
    return redirect("qms:document_detail", number=number)


@qms_member
@require_POST
def requirement_remove(request, pk):
    req = get_object_or_404(TrainingRequirement, pk=pk)
    require_access(request, req.document.device)
    if services.user_has_role(request.user, [wf.QA], req.document.device):
        req.active = False
        req.save()
        messages.success(request, f"Requirement removed: {req}.")
    else:
        messages.error(request, "Requires role: QA.")
    return redirect("qms:document_detail", number=req.document.number)


# --- training ---------------------------------------------------------------------------

@qms_member
def my_training(request):
    assignments = TrainingAssignment.objects.filter(user=request.user).select_related(
        "version__document").order_by("completed_at", "due_date")
    return render(request, "qms/my_training.html", {"assignments": assignments,
                                                    "sign_form": SignForm()})


@qms_member
@require_POST
def training_complete(request, pk):
    a = get_object_or_404(TrainingAssignment, pk=pk)
    form = SignForm(request.POST)
    form.is_valid()
    run(request, services.complete_training, a, request.user,
        form.cleaned_data.get("password", ""), success=f"Training on {a.version} recorded.")
    return redirect("qms:my_training")


@qms_member
def training_matrix(request):
    docs, rows = services.training_matrix(viewer=request.user)
    return render(request, "qms/training_matrix.html", {"docs": docs, "rows": rows})


@qms_member
def document_export(request):
    """Every effective document you can see, as a zip of folders (see qms.doc_exchange)."""
    data = doc_exchange.export_zip(request.user)
    response = HttpResponse(data, content_type="application/zip")
    response["Content-Disposition"] = (
        f'attachment; filename="qms-documents-{date.today():%Y%m%d}.zip"')
    return response


@qms_member
def document_import(request):
    """Import markdown documents, or draft revisions of existing ones."""
    results = None
    if request.method == "POST":
        uploads = [(f.name, f.read()) for f in request.FILES.getlist("files")]
        if not uploads:
            messages.error(request, "Choose at least one markdown file or zip archive.")
        else:
            try:
                results = doc_exchange.import_markdown(request.user, uploads)
            except TransitionError as exc:
                for err in exc.errors:
                    messages.error(request, err)
    return render(request, "qms/document_import.html", {
        "form": DocumentImportForm(), "results": results})

