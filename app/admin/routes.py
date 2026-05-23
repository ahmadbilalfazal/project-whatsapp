import os
from flask import render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.admin import bp
from app.ingest import ingest_file
from app.forms import UploadForm
from app.models import Chunk, Conversation, Document, Message



def _upload_folder():
    folder = current_app.config.get('UPLOAD_FOLDER') or os.path.join(os.path.dirname(__file__), '..', '..', 'uploads')
    os.makedirs(folder, exist_ok=True)
    return folder


@bp.route('/admin')
@login_required
def index():
    business = getattr(current_user, 'business', None)
    if business is None:
        stats = {'documents': 0, 'chunks': 0, 'conversations': 0, 'messages': 0}
        return render_template('admin_index.html', stats=stats, recent_documents=[], recent_conversations=[], business=None)
    stats = {
        'documents': Document.query.filter_by(business_id=business.id).count(),
        'chunks': Chunk.query.filter_by(business_id=business.id).count(),
        'conversations': Conversation.query.filter_by(business_id=business.id).count(),
        'messages': Message.query.filter_by(business_id=business.id).count(),
    }
    recent_documents = Document.query.filter_by(business_id=business.id).order_by(Document.uploaded_at.desc()).limit(5).all()
    recent_conversations = Conversation.query.filter_by(business_id=business.id).order_by(Conversation.last_message_at.desc()).limit(5).all()
    return render_template('admin_index.html', stats=stats, recent_documents=recent_documents, recent_conversations=recent_conversations, business=business)


@bp.route('/admin/upload', methods=['GET', 'POST'])
@login_required
def upload():
    form = UploadForm()
    if form.validate_on_submit():
        f = form.file.data
        filename = secure_filename(f.filename)
        path = os.path.join(_upload_folder(), filename)
        f.save(path)
        with open(path, 'rb') as fh:
            try:
                result = ingest_file(fh, filename, business.id if business else None)
                flash(f'Indexed {filename}: document #{result["doc_id"]} with {result["chunks"]} chunks')
            except Exception as e:
                flash(f'Error ingesting file: {e}')
        return redirect(url_for('admin.index'))
    return render_template('admin_upload.html', form=form)
