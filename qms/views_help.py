"""In-app help. Open to everyone, signed in or not: it contains no QMS data."""
from django.http import Http404
from django.shortcuts import render
from django.utils.safestring import mark_safe

from . import help as qms_help


def help_index(request):
    return render(request, "qms/help.html", {
        "topics": qms_help.TOPICS, "topic": None, "title": "Help",
    })


def help_topic(request, topic):
    if topic not in qms_help.TOPIC_TITLES:
        raise Http404("No such help topic.")
    html, toc = qms_help.render_topic(topic)
    return render(request, "qms/help.html", {
        "topics": qms_help.TOPICS, "topic": topic, "title": qms_help.TOPIC_TITLES[topic],
        "content": mark_safe(html),  # rendered from the help files shipped with the app
        "toc": [t for t in toc if t["level"] == 2],
    })
