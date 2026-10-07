#!/usr/bin/env python3
"""Create a Google Form from a JSON spec.

    python create_form.py spec.json [--share you@example.com]

Spec: {"title", "documentTitle"?, "description"?, "items": [
  {"title", "type": "text"|"paragraph"|"radio"|"checkbox"|"dropdown",
   "description"?, "required"?: bool, "options"?: [str, ...]}]}

Auth: user ADC by default (gcloud auth application-default login --scopes=...forms.body);
the form is then owned by that user. --sa PATH uses a service account instead, which
only works with domain-wide delegation (plain SAs get a 500 from forms.create).
"""
import json
import os
import sys

import google.auth

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/forms.body",
          "https://www.googleapis.com/auth/drive"]
CHOICE_TYPES = {"radio": "RADIO", "checkbox": "CHECKBOX", "dropdown": "DROP_DOWN"}


def _question(item):
    q = {"required": bool(item.get("required"))}
    t = item.get("type", "text")
    if t in CHOICE_TYPES:
        q["choiceQuestion"] = {
            "type": CHOICE_TYPES[t],
            "options": [{"value": o} for o in item["options"]],
        }
    else:
        q["textQuestion"] = {"paragraph": t == "paragraph"}
    return q


def create(spec, sa_path=None, share=None):
    if sa_path:
        # NOTE: service accounts get HTTP 500 from forms.create unless they act
        # via domain-wide delegation. Prefer user ADC (sa_path=None).
        creds = service_account.Credentials.from_service_account_file(sa_path, scopes=SCOPES)
    else:
        creds, _ = google.auth.default(scopes=SCOPES)
    forms = build("forms", "v1", credentials=creds)
    form = forms.forms().create(body={"info": {
        "title": spec["title"],
        "documentTitle": spec.get("documentTitle", spec["title"]),
    }}).execute()
    fid = form["formId"]

    requests = []
    if spec.get("description"):
        requests.append({"updateFormInfo": {
            "info": {"description": spec["description"]},
            "updateMask": "description"}})
    for i, item in enumerate(spec.get("items", [])):
        body = {"title": item["title"],
                "questionItem": {"question": _question(item)}}
        if item.get("description"):
            body["description"] = item["description"]
        requests.append({"createItem": {"item": body, "location": {"index": i}}})
    if requests:
        forms.forms().batchUpdate(formId=fid, body={"requests": requests}).execute()

    if share:
        build("drive", "v3", credentials=creds).permissions().create(
            fileId=fid, sendNotificationEmail=False,
            body={"type": "user", "role": "writer", "emailAddress": share},
        ).execute()
    return forms.forms().get(formId=fid).execute()


def main(argv):
    args = list(argv)

    def opt(name):
        if name in args:
            i = args.index(name)
            del args[i]
            return args.pop(i)
        return None

    share = opt("--share")
    sa = opt("--sa")
    if len(args) != 1:
        sys.exit(__doc__)
    with open(args[0]) as fh:
        spec = json.load(fh)
    form = create(spec, sa, share)
    print("edit:      " + form["responderUri"].replace("/viewform", "").replace(
        "https://docs.google.com/forms/d/e/", "https://docs.google.com/forms/d/") )
    print("formId:    " + form["formId"])
    print("responder: " + form["responderUri"])


def demo():
    assert _question({"type": "radio", "options": ["a", "b"], "required": True}) == {
        "required": True,
        "choiceQuestion": {"type": "RADIO", "options": [{"value": "a"}, {"value": "b"}]}}
    assert _question({}) == {"required": False, "textQuestion": {"paragraph": False}}
    assert _question({"type": "paragraph"})["textQuestion"]["paragraph"] is True
    print("ok")


if __name__ == "__main__":
    (demo if sys.argv[1:2] == ["--demo"] else lambda: main(sys.argv[1:]))()
