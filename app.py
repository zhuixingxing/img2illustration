#!/usr/bin/env python3
"""
图片转插画 Web 应用
启动: python app.py
访问: http://localhost:5000
"""

import io, base64, os
from flask import Flask, request, jsonify
from PIL import Image
from illustrate import process_image, STYLES

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB 上限

HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>图片转插画</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --accent: #6366f1; --accent-dark: #4f46e5;
      --green: #10b981; --green-dark: #059669;
      --bg: #f0f2f7; --surface: #ffffff;
      --border: #e4e7ef; --text: #1e1e2e; --muted: #6b7280;
      --radius: 14px; --shadow: 0 2px 16px rgba(0,0,0,.07);
    }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
    header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 18px 40px; display: flex; align-items: center; gap: 14px; }
    .logo { font-size: 28px; }
    header h1 { font-size: 20px; font-weight: 700; letter-spacing: -.02em; }
    header p  { font-size: 13px; color: var(--muted); margin-top: 2px; }
    .wrap { max-width: 980px; margin: 36px auto; padding: 0 20px; }
    .card { background: var(--surface); border-radius: var(--radius); padding: 28px 32px; box-shadow: var(--shadow); margin-bottom: 20px; }
    .card-title { font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-bottom: 18px; }
    .upload-zone { border: 2px dashed var(--border); border-radius: 10px; padding: 44px 20px; text-align: center; cursor: pointer; transition: border-color .2s, background .2s; }
    .upload-zone:hover, .upload-zone.drag-over { border-color: var(--accent); background: #f5f5ff; }
    .upload-zone input { display: none; }
    .upload-zone .icon { font-size: 44px; line-height: 1; margin-bottom: 12px; }
    .upload-zone .hint { font-size: 15px; font-weight: 500; }
    .upload-zone .sub  { font-size: 13px; color: var(--muted); margin-top: 6px; }
    .upload-zone.has-file { border-style: solid; border-color: var(--accent); background: #f5f5ff; }
    .style-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
    @media (max-width: 520px) { .style-grid { grid-template-columns: 1fr; } }
    .style-card { border: 2px solid var(--border); border-radius: 10px; padding: 18px 14px; text-align: center; cursor: pointer; transition: border-color .2s, background .2s, transform .15s; user-select: none; }
    .style-card:hover { border-color: var(--accent); transform: translateY(-2px); }
    .style-card.active { border-color: var(--accent); background: #f0f0ff; }
    .style-card .s-icon { font-size: 32px; margin-bottom: 8px; display: block; }
    .style-card .s-name { font-weight: 700; font-size: 14px; }
    .style-card .s-desc { font-size: 12px; color: var(--muted); margin-top: 4px; line-height: 1.4; }
    .style-card.active .s-desc { color: #8080cc; }
    .slider-row { display: flex; align-items: center; gap: 14px; }
    .slider-row label { white-space: nowrap; font-size: 14px; font-weight: 600; min-width: 80px; }
    input[type=range] { flex: 1; accent-color: var(--accent); }
    .slider-val { min-width: 68px; text-align: right; font-size: 14px; font-weight: 700; color: var(--accent); }
    .btn-convert { width: 100%; padding: 15px; background: var(--accent); color: #fff; border: none; border-radius: 10px; font-size: 16px; font-weight: 700; cursor: pointer; transition: background .2s, transform .1s; }
    .btn-convert:hover:not(:disabled) { background: var(--accent-dark); transform: translateY(-1px); }
    .btn-convert:disabled { opacity: .45; cursor: not-allowed; }
    .progress { display: none; margin-top: 16px; }
    .progress-track { height: 5px; background: var(--border); border-radius: 5px; overflow: hidden; }
    .progress-fill { height: 100%; background: var(--accent); animation: slide 1.3s ease-in-out infinite; }
    @keyframes slide { 0%{width:0;margin-left:0} 50%{width:55%;margin-left:22%} 100%{width:0;margin-left:100%} }
    .progress-label { text-align: center; font-size: 13px; color: var(--muted); margin-top: 8px; }
    .error { display: none; margin-top: 14px; background: #fef2f2; border: 1px solid #fecaca; color: #dc2626; border-radius: 8px; padding: 11px 16px; font-size: 14px; }
    #result-card { display: none; }
    .compare { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    @media (max-width: 600px) { .compare { grid-template-columns: 1fr; } }
    .compare-col h3 { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-bottom: 10px; }
    .compare-col img { width: 100%; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,.1); display: block; }
    .btn-dl { display: inline-flex; align-items: center; gap: 6px; margin-top: 12px; padding: 9px 20px; background: var(--green); color: #fff; border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: 600; transition: background .2s; }
    .btn-dl:hover { background: var(--green-dark); }
  </style>
</head>
<body>
<header>
  <div class="logo">🎨</div>
  <div>
    <h1>图片转插画</h1>
    <p>纯算法实现 · 本地运行 · 无需 AI 服务</p>
  </div>
</header>
<div class="wrap">
  <div class="card">
    <div class="card-title">上传图片</div>
    <div class="upload-zone" id="drop-zone">
      <input type="file" id="file-input" accept="image/*">
      <div class="icon">🖼️</div>
      <div class="hint" id="hint-text">点击选择 或 拖拽图片到此处</div>
      <div class="sub">支持 JPG · PNG · WEBP · 最大 20 MB</div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">选择风格</div>
    <div class="style-grid">
      <div class="style-card active" data-style="cartoon">
        <span class="s-icon">🎨</span>
        <div class="s-name">卡通插画</div>
        <div class="s-desc">平涂色块 + 清晰黑色轮廓</div>
      </div>
      <div class="style-card" data-style="sketch">
        <span class="s-icon">✏️</span>
        <div class="s-name">铅笔素描</div>
        <div class="s-desc">颜色减淡混合算法</div>
      </div>
      <div class="style-card" data-style="watercolor">
        <span class="s-icon">💧</span>
        <div class="s-name">水彩画</div>
        <div class="s-desc">柔和扩散 + 纸张纹理</div>
      </div>
    </div>
    <div style="margin-top: 24px;">
      <div class="card-title" style="margin-bottom: 12px;">处理尺寸</div>
      <div class="slider-row">
        <label>最大边长</label>
        <input type="range" id="max-size" min="256" max="2048" step="128" value="1024">
        <div class="slider-val"><span id="size-num">1024</span> px</div>
      </div>
    </div>
  </div>
  <div class="card">
    <button class="btn-convert" id="btn-convert" disabled>请先选择图片</button>
    <div class="progress" id="progress">
      <div class="progress-track"><div class="progress-fill"></div></div>
      <div class="progress-label" id="progress-label">处理中，请稍候…</div>
    </div>
    <div class="error" id="error-box"></div>
  </div>
  <div class="card" id="result-card">
    <div class="card-title">处理结果</div>
    <div class="compare">
      <div class="compare-col">
        <h3>原图</h3>
        <img id="img-original" src="" alt="原图">
      </div>
      <div class="compare-col">
        <h3>插画效果</h3>
        <img id="img-result" src="" alt="结果">
        <a id="btn-dl" class="btn-dl" href="#" download="illustration.png">⬇ 下载插画</a>
      </div>
    </div>
  </div>
</div>
<script>
  let file = null, style = 'cartoon';
  document.querySelectorAll('.style-card').forEach(card => {
    card.addEventListener('click', () => {
      document.querySelectorAll('.style-card').forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      style = card.dataset.style;
    });
  });
  const slider = document.getElementById('max-size');
  const sizeNum = document.getElementById('size-num');
  slider.addEventListener('input', () => sizeNum.textContent = slider.value);
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  dropZone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', e => setFile(e.target.files[0]));
  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', e => { e.preventDefault(); dropZone.classList.remove('drag-over'); setFile(e.dataTransfer.files[0]); });
  function setFile(f) {
    if (!f || !f.type.startsWith('image/')) return;
    file = f;
    dropZone.classList.add('has-file');
    document.getElementById('hint-text').textContent = `✅  ${f.name}  (${(f.size/1024).toFixed(0)} KB)`;
    document.getElementById('btn-convert').disabled = false;
    document.getElementById('btn-convert').textContent = '开始转换';
    const reader = new FileReader();
    reader.onload = e => document.getElementById('img-original').src = e.target.result;
    reader.readAsDataURL(f);
  }
  document.getElementById('btn-convert').addEventListener('click', async () => {
    if (!file) return;
    const btn = document.getElementById('btn-convert');
    const progress = document.getElementById('progress');
    const errorBox = document.getElementById('error-box');
    const resultCard = document.getElementById('result-card');
    btn.disabled = true; btn.textContent = '处理中…';
    progress.style.display = 'block'; errorBox.style.display = 'none'; resultCard.style.display = 'none';
    const steps = { cartoon:['平滑色彩…','色彩海报化…','提取轮廓…','合成中…'], sketch:['转灰度…','颜色减淡混合…','调整对比度…'], watercolor:['软化色彩…','添加纹理…','柔化轮廓…','合成中…'] };
    const label = document.getElementById('progress-label');
    let si = 0;
    const timer = setInterval(() => { const list = steps[style]||['处理中…']; label.textContent = list[si++ % list.length]; }, 900);
    try {
      const fd = new FormData();
      fd.append('image', file); fd.append('style', style); fd.append('max_size', slider.value);
      const resp = await fetch('/convert', { method: 'POST', body: fd });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
      document.getElementById('img-result').src = data.image;
      document.getElementById('btn-dl').href = data.image;
      document.getElementById('btn-dl').download = `illustration_${style}.png`;
      resultCard.style.display = 'block';
      resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) {
      errorBox.textContent = '转换失败：' + err.message;
      errorBox.style.display = 'block';
    } finally {
      clearInterval(timer);
      btn.disabled = false; btn.textContent = '重新转换';
      progress.style.display = 'none';
    }
  });
</script>
</body>
</html>"""


@app.route('/')
def index():
    return HTML


@app.route('/convert', methods=['POST'])
def convert():
    f = request.files.get('image')
    if not f:
        return jsonify({'error': '未收到图片文件'}), 400

    style = request.form.get('style', 'cartoon')
    if style not in STYLES:
        return jsonify({'error': f'不支持的风格: {style}'}), 400

    try:
        max_size = int(request.form.get('max_size', 1024))
        max_size = max(64, min(max_size, 4096))
    except ValueError:
        max_size = 1024

    try:
        img = Image.open(f.stream)
        result = process_image(img, style=style, max_size=max_size)
        buf = io.BytesIO()
        result.save(buf, format='PNG', optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return jsonify({'image': f'data:image/png;base64,{b64}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f'\n  本地访问: http://localhost:{port}\n')
    app.run(host='0.0.0.0', port=port, debug=False)
