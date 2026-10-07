"""Upload a local folder to Google Drive, preserving structure.

    python upload_folder.py <local-folder> [--name "Drive folder name"] [--share anyone]

Uses Application Default Credentials (gcloud auth application-default login).
Needs the drive.file scope. Prints the folder's shareable link.
Files are uploaded byte-for-byte; nothing is converted or recompressed.
"""
import sys, os, mimetypes
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

FOLDER = 'application/vnd.google-apps.folder'


def mkdir(svc, name, parent=None):
    body = {'name': name, 'mimeType': FOLDER}
    if parent:
        body['parents'] = [parent]
    return svc.files().create(body=body, fields='id').execute()['id']


def push(svc, local, parent):
    n = 0
    for entry in sorted(os.listdir(local)):
        if entry.startswith('.'):
            continue
        path = os.path.join(local, entry)
        if os.path.isdir(path):
            n += push(svc, path, mkdir(svc, entry, parent))
        else:
            mime = mimetypes.guess_type(path)[0] or 'application/octet-stream'
            svc.files().create(
                body={'name': entry, 'parents': [parent]},
                media_body=MediaFileUpload(path, mimetype=mime, resumable=True),
                fields='id').execute()
            n += 1
            print(f'  {entry}', file=sys.stderr)
    return n


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        print(__doc__); return
    local = args[0].rstrip('/')
    name = sys.argv[sys.argv.index('--name') + 1] if '--name' in sys.argv else os.path.basename(local)
    share = sys.argv[sys.argv.index('--share') + 1] if '--share' in sys.argv else None

    creds, _ = google.auth.default()
    svc = build('drive', 'v3', credentials=creds, cache_discovery=False)
    root = mkdir(svc, name)
    n = push(svc, local, root)

    if share == 'anyone':
        svc.permissions().create(fileId=root,
                                 body={'type': 'anyone', 'role': 'reader'}).execute()
    print(f'\n{n} files uploaded')
    print(f'https://drive.google.com/drive/folders/{root}')


if __name__ == '__main__':
    main()
