// Simple drag-and-drop and client-side validation for admin upload
document.addEventListener('DOMContentLoaded', function(){
  const dropzone = document.getElementById('dropzone');
  if (!dropzone) return;
  const fileInput = document.getElementById('file-input');
  const form = document.getElementById('upload-form');
  const info = document.getElementById('dz-info');
  const errorEl = document.getElementById('dz-error');
  const allowed = ['pdf','docx','txt'];
  const maxBytes = 10 * 1024 * 1024; // 10 MB

  function showError(msg){
    if(errorEl){ errorEl.textContent = msg; errorEl.style.display='block'; }
  }
  function clearError(){ if(errorEl){ errorEl.textContent=''; errorEl.style.display='none'; } }

  dropzone.addEventListener('click', ()=> fileInput.click());
  dropzone.addEventListener('dragover', (e)=>{ e.preventDefault(); dropzone.classList.add('dragover'); });
  dropzone.addEventListener('dragleave', ()=>{ dropzone.classList.remove('dragover'); });
  dropzone.addEventListener('drop', (e)=>{
    e.preventDefault(); dropzone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if(files.length) handleFiles(files);
  });

  fileInput.addEventListener('change', ()=>{
    handleFiles(fileInput.files);
  });

  function handleFiles(files){
    clearError();
    const f = files[0];
    if(!f){ showError('No file selected'); return; }
    const ext = f.name.split('.').pop().toLowerCase();
    if(!allowed.includes(ext)) { showError('Unsupported file type. Use PDF, DOCX, or TXT.'); return; }
    if(f.size > maxBytes){ showError('File too large. Max 10 MB.'); return; }
    // show selected name
    if(info) info.textContent = f.name + ' (' + Math.round(f.size/1024) + ' KB)';
    // put file into real input (already in fileInput)
  }

  // optional: intercept form submit to revalidate
  if(form){
    form.addEventListener('submit', function(e){
      clearError();
      const f = fileInput.files[0];
      if(!f){ e.preventDefault(); showError('Please choose a file to upload.'); return; }
      const ext = f.name.split('.').pop().toLowerCase();
      if(!allowed.includes(ext)){ e.preventDefault(); showError('Unsupported file type.'); return; }
      if(f.size > maxBytes){ e.preventDefault(); showError('File too large.'); return; }
    });
  }
});
