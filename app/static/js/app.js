/* PyMaster frontend runtime */
(function () {
  'use strict';

  var PyMaster = (window.PyMaster = window.PyMaster || {});

  /* ─────────────────────────── helpers ─────────────────────────── */
  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function postForm(url, fields) {
    var body = new URLSearchParams();
    Object.keys(fields).forEach(function (k) { body.append(k, fields[k]); });
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
      credentials: 'same-origin',
    });
  }

  /* ─────────────────────── input modal ─────────────────────────── */
  function openInputModal(prompt, onDone) {
    var mask = document.getElementById('input-modal');
    if (!mask) { onDone(''); return; }
    var label = document.getElementById('input-prompt');
    var field = document.getElementById('input-field');
    var okBtn = document.getElementById('input-ok');
    var cancelBtn = document.getElementById('input-cancel');
    if (label) label.textContent = prompt || '';
    if (field) field.value = '';
    mask.hidden = false;
    if (field) field.focus();
    function finish() {
      mask.hidden = true;
      if (okBtn) okBtn.removeEventListener('click', finish);
      if (field) field.removeEventListener('keydown', onKey);
      if (cancelBtn) cancelBtn.removeEventListener('click', cancel);
      onDone(field ? field.value : '');
    }
    function cancel() {
      mask.hidden = true;
      if (okBtn) okBtn.removeEventListener('click', finish);
      if (field) field.removeEventListener('keydown', onKey);
      if (cancelBtn) cancelBtn.removeEventListener('click', cancel);
      onDone('');
    }
    function onKey(e) { if (e.key === 'Enter') finish(); }
    if (okBtn) okBtn.addEventListener('click', finish);
    if (field) field.addEventListener('keydown', onKey);
    if (cancelBtn) cancelBtn.addEventListener('click', cancel);
  }

  /* ─────────────────── Python syntax highlight ─────────────────── */
  var KW =
    'and|as|assert|async|await|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|return|True|try|while|with|yield';

  function pyHighlight(code) {
    var e = esc(code);
    var re = new RegExp(
      '(#[^\\n]*)|' +
      "(f?\"[^\"\\n]*\"|f?'[^'\\n]*'|\"[^\"\\n]*\"|'[^'\\n]*')|" +
      '(\\bdef\\s+)(\\w+)|' +
      '(\\b(?:' + KW + ')\\b)|' +
      '(\\b\\d+(?:\\.\\d+)?\\b)|' +
      '(\\b(?:print|input|len|int|float|str|bool|list|range|type|sum|min|max)\\b)',
      'g'
    );
    return e.replace(re, function (m, com, str, dws, fname, kw, num, bf) {
      if (com !== undefined) return '<span class="tok-com">' + com + '</span>';
      if (str !== undefined) return '<span class="tok-str">' + str + '</span>';
      if (dws !== undefined) return dws + '<span class="tok-fn">' + fname + '</span>';
      if (kw !== undefined) return '<span class="tok-kw">' + kw + '</span>';
      if (num !== undefined) return '<span class="tok-num">' + num + '</span>';
      if (bf !== undefined) return '<span class="tok-bf">' + bf + '</span>';
      return m;
    });
  }

  /* ─────────────────────── code editor objects ─────────────────── */
  var editors = {};

  function initEditor(container, textarea) {
    var wrapper = textarea.closest('.code-editor');
    if (!wrapper) wrapper = textarea.closest('.lab-editor');
    var hl = wrapper.querySelector('pre.hl');
    if (!hl) {
      hl = document.createElement('pre');
      hl.className = 'hl';
      hl.setAttribute('aria-hidden', 'true');
      wrapper.insertBefore(hl, textarea);
    }
    var minH = wrapper.classList.contains('lab-editor') ? 380 : 130;
    function autosize() {
      textarea.style.height = 'auto';
      textarea.style.height = Math.max(textarea.scrollHeight, minH) + 'px';
    }
    function update() {
      var raw = textarea.value;
      var rows = raw === '' ? [''] : (raw + '\n').split('\n');
      var out = [];
      for (var i = 0; i < rows.length; i++) {
        out.push('<span class="ln">' + (i + 1) + '</span>' + (pyHighlight(rows[i]) || ''));
      }
      hl.innerHTML = out.join('\n');
      autosize();
    }
    textarea.addEventListener('input', update);
    textarea.addEventListener('scroll', function () {
      hl.scrollTop = textarea.scrollTop;
      hl.scrollLeft = textarea.scrollLeft;
    });
    update();
    editors[container] = { textarea: textarea, hl: hl };
  }

  function eachEditor(root) {
    var list = (root || document).querySelectorAll('.code-editor textarea.editor, .lab-editor textarea#lab-code');
    Array.prototype.forEach.call(list, function (ta) {
      initEditor(ta.getAttribute('data-editor') || ta.id, ta);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    eachEditor(document);
    initLab();
  });
  document.addEventListener('htmx:afterSwap', function (e) { eachEditor(e.target); });

  /* ─────────────────────── exercise actions ───────────────────── */
  function exId(container) {
    return String(container).replace(/^ex-/, '');
  }

  function runEditor(code, id, inputs) {
    if (inputs.length > 50) return;
    postForm('/frag/exercise/' + id + '/run', { code: code, stdin: inputs.join('\n') }).then(function (r) {
      return r.text();
    }).then(function (html) {
      var el = document.getElementById('console-ex-' + id);
      if (el) el.innerHTML = html;
      var pending = el ? el.querySelector('[data-input-prompt]') : null;
      if (pending) {
        openInputModal(pending.getAttribute('data-input-prompt') || '', function (value) {
          if (value === '') return;
          inputs.push(value);
          runEditor(code, id, inputs);
        });
      }
    });
  }

  PyMaster.editorRun = function (container) {
    var ta = document.querySelector('#' + container + ' .editor, #' + container + ' textarea[name=code]');
    if (!ta) return;
    runEditor(ta.value, exId(container), []);
  };

  PyMaster.editorVerify = function (container) {
    var ta = document.querySelector('#' + container + ' textarea[name=code]');
    if (!ta) return;
    var id = exId(container);
    postForm('/frag/exercise/' + id + '/answer', { code: ta.value }).then(function (r) {
      return r.text();
    }).then(function (html) {
      var el = document.getElementById('fb-' + id);
      if (el) {
        el.innerHTML = html;
        afterAnswerSwap(el);
      }
    });
  };

  PyMaster.editorVisualize = function (container) {
    var ta = document.querySelector('#' + container + ' textarea[name=code]');
    if (!ta) return;
    PyMaster.openVisualizer(ta.value);
  };

  var hintsUsed = {};
  PyMaster.nextHint = function (container) {
    var id = exId(container);
    var lvl = (hintsUsed[id] || 0) + 1;
    hintsUsed[id] = lvl;
    postForm('/frag/exercise/' + id + '/hint', { hint_level: lvl }).then(function (r) {
      return r.text();
    }).then(function (html) {
      var el = document.getElementById('hint-ex-' + id);
      if (el) el.innerHTML = html;
    });
  };

  PyMaster.visualizeFromCode = function (exerciseId) {
    var card = document.getElementById('ex-' + exerciseId);
    if (!card || !card.dataset.code) return;
    PyMaster.openVisualizer(card.dataset.code);
  };

  /* ─────────────────────── order exercises ─────────────────────── */
  function orderItemIndex(btn, dir) {
    var wrap = btn.closest('.order-wrap');
    var list = wrap.querySelector('.order-list');
    var items = Array.prototype.slice.call(list.children);
    var cur = btn.closest('.order-item');
    var idx = items.indexOf(cur);
    var target = idx + dir;
    if (target < 0 || target >= items.length) return;
    if (dir < 0) list.insertBefore(items[idx], items[target]);
    else list.insertBefore(items[target], items[idx]);
    renumber(wrap);
  }
  function lineText(it) {
    var t = it.querySelector('.order-text');
    return t ? t.textContent : it.textContent;
  }
  function renumber(wrap) {
    var inputs = wrap.querySelectorAll('.order-item');
    inputs.forEach(function (it, i) {
      var num = it.querySelector('.order-num');
      if (num) num.textContent = i + 1 + '.';
    });
    var vals = [];
    inputs.forEach(function (it) {
      vals.push(lineText(it).replace(/^\s*\d+\.\s*/, ''));
    });
    var hid = wrap.querySelector('input[name=answer]');
    if (hid) hid.value = vals.join('\n');
  }
  PyMaster.orderUp = function (b) { orderItemIndex(b, -1); };
  PyMaster.orderDn = function (b) { orderItemIndex(b, 1); };

  var dragItem = null;

  function orderListFor(item) {
    return item.closest('.order-list');
  }

  document.addEventListener('dragstart', function (e) {
    var it = e.target.closest('.order-item');
    if (!it) return;
    dragItem = it;
    it.classList.add('dragging');
    if (typeof e.dataTransfer !== 'undefined') {
      e.dataTransfer.effectAllowed = 'move';
      try { e.dataTransfer.setData('text/plain', ''); } catch (err) {}
    }
  });

  document.addEventListener('dragover', function (e) {
    if (!dragItem) return;
    var list = orderListFor(e.target);
    if (!list) return;
    e.preventDefault();
    if (typeof e.dataTransfer !== 'undefined') e.dataTransfer.dropEffect = 'move';
    list.classList.add('drop-target');
    var target = e.target.closest('.order-item');
    if (target && target !== dragItem) {
      var after = (e.clientY - target.getBoundingClientRect().top) > (target.offsetHeight / 2);
      if (after) list.insertBefore(dragItem, target.nextSibling);
      else list.insertBefore(dragItem, target);
      renumber(dragItem.closest('.order-wrap'));
    }
  });

  document.addEventListener('dragleave', function (e) {
    var list = orderListFor(e.target);
    if (list && !list.contains(e.relatedTarget)) list.classList.remove('drop-target');
  });

  document.addEventListener('drop', function (e) {
    if (!dragItem) return;
    var list = orderListFor(e.target);
    if (!list) return;
    e.preventDefault();
    list.classList.remove('drop-target');
    dragItem.classList.remove('dragging');
    renumber(dragItem.closest('.order-wrap'));
    dragItem = null;
  });

  document.addEventListener('dragend', function () {
    if (!dragItem) return;
    dragItem.classList.remove('dragging');
    var list = orderListFor(dragItem);
    renumber(dragItem.closest('.order-wrap'));
    if (list) list.classList.remove('drop-target');
    dragItem = null;
  });

  /* ───────────────── navigation entre exercícios ──────────────── */
  function afterAnswerSwap(zone) {
    if (!zone || !zone.closest) return;
    var card = zone.closest('.exercise-card');
    if (!card) return;
    var fb = card.querySelector('.feedback[data-solved="1"]');
    if (!fb) return;
    var btn = card.querySelector('.btn-next');
    if (btn) btn.disabled = false;
    var note = card.querySelector('.next-note');
    if (note && note.parentNode) note.parentNode.removeChild(note);
    var chip = card.querySelector('.ex-solved');
    if (!chip) {
      chip = document.createElement('span');
      chip.className = 'ex-solved';
      chip.textContent = '✓ Resolvido';
      var head = card.querySelector('.ex-head');
      if (head) head.appendChild(chip);
    }
  }
  document.addEventListener('click', function (e) {
    var btn = e.target && e.target.closest ? e.target.closest('.btn-next') : null;
    if (!btn || btn.disabled) return;
    var jump = btn.getAttribute('data-jump');
    if (jump) {
      e.preventDefault();
      var target = document.querySelector(jump);
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      history.replaceState(null, '', jump);
      return;
    }
    var href = btn.getAttribute('data-href');
    if (href) window.location.href = href;
  });
  document.addEventListener('htmx:afterSwap', function (e) {
    var elt = e.detail && e.detail.elt;
    if (!elt || !elt.closest) return;
    var card = elt.closest('.exercise-card');
    if (!card) return;
    afterAnswerSwap(card.querySelector('.feedback-zone'));
  });

  /* ─────────────────────── review confetti ────────────────────── */
  function confettiBurst() {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var colors = ['#f59e0b', '#22c55e', '#3b82f6', '#ec4899', '#8b5cf6', '#ef4444', '#10b981'];
    var layer = document.createElement('div');
    layer.className = 'confetti-layer';
    layer.setAttribute('aria-hidden', 'true');
    for (var i = 0; i < 90; i++) {
      var c = document.createElement('span');
      c.className = 'confetti';
      c.style.left = (Math.random() * 100).toFixed(2) + '%';
      c.style.width = (6 + Math.random() * 7).toFixed(1) + 'px';
      c.style.height = (6 + Math.random() * 7).toFixed(1) + 'px';
      c.style.backgroundColor = colors[i % colors.length];
      c.style.borderRadius = Math.random() > 0.5 ? '50%' : '2px';
      c.style.animationDuration = (2200 + Math.random() * 1800).toFixed(0) + 'ms';
      c.style.animationDelay = (Math.random() * 400).toFixed(0) + 'ms';
      c.style.setProperty('--confetti-x', (Math.random() * 220 - 110).toFixed(0) + 'px');
      c.style.setProperty('--confetti-r', (Math.random() * 540 - 180).toFixed(0) + 'deg');
      layer.appendChild(c);
    }
    document.body.appendChild(layer);
    setTimeout(function () {
      if (layer && layer.parentNode) layer.parentNode.removeChild(layer);
    }, 6000);
  }
  document.addEventListener('htmx:afterSwap', function (e) {
    var el = e.target;
    if (el && el.querySelector && el.querySelector('[data-confetti]')) confettiBurst();
  });

  /* ─────────────────────── pin modal (seletor de perfis) ─────── */
  var pinForm = null;

  function openPinModal(form, showError) {
    var mask = document.getElementById('pin-modal');
    if (!mask) return;
    pinForm = form;
    var err = document.getElementById('pin-error');
    var field = document.getElementById('pin-input');
    if (err) err.hidden = !showError;
    if (field) field.value = '';
    mask.hidden = false;
    if (field) field.focus();
  }

  function closePinModal() {
    var mask = document.getElementById('pin-modal');
    if (mask) mask.hidden = true;
  }

  function submitPin() {
    var mask = document.getElementById('pin-modal');
    if (!mask || !pinForm) return;
    var field = document.getElementById('pin-input');
    var hidden = pinForm.querySelector('input[name="pin"]');
    if (hidden && field) hidden.value = field.value;
    mask.hidden = true;
    pinForm.submit();
  }

  function pickerErrorMessage() {
    var params = new URLSearchParams(location.search);
    if (params.get('error') === 'pin' && params.get('pin')) return params.get('pin');
    return null;
  }

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (form && form.matches && form.matches('[data-needs-pin]')) {
      e.preventDefault();
      openPinModal(form, false);
    }
  }, true);

  document.addEventListener('click', function (e) {
    var btn = e.target && e.target.closest ? e.target.closest('.pin-form button[type="submit"]') : null;
    if (btn) {
      e.preventDefault();
      openPinModal(btn.closest('form'), false);
    }
  });

  document.addEventListener('DOMContentLoaded', function () {
    var mask = document.getElementById('pin-modal');
    if (!mask) return;
    var ok = document.getElementById('pin-ok');
    var cancel = document.getElementById('pin-cancel');
    var field = document.getElementById('pin-input');
    if (ok) ok.addEventListener('click', submitPin);
    if (cancel) cancel.addEventListener('click', closePinModal);
    if (field) field.addEventListener('keydown', function (e) { if (e.key === 'Enter') submitPin(); });
    var pid = pickerErrorMessage();
    if (pid) {
      var f = document.querySelector('.pin-form') || document.querySelector('form[data-pin-id="' + pid + '"]');
      if (f) openPinModal(f, true);
    }
  });

  /* ─────────────────────── theme / menu ────────────────────────── */
  var root = document.documentElement;
  function applyTheme() {
    root.setAttribute('data-theme', root.getAttribute('data-theme') === 'light' ? 'dark' : 'light');
  }
  document.addEventListener('DOMContentLoaded', function () {
    var toggle = document.getElementById('theme-toggle');
    if (toggle) {
      toggle.addEventListener('click', function () {
        applyTheme();
        if (toggle.dataset.logged === '1') postForm('/frag/settings/toggle', { key: 'theme' });
      });
    }
    var menuBtn = document.getElementById('menu-btn');
    if (menuBtn) {
      menuBtn.addEventListener('click', function () {
        document.querySelector('.sidebar').classList.toggle('open');
      });
    }
  });

  /* ─────────────────────── visualizer modal ────────────────────── */
  var viz = {
    steps: [],
    idx: 0,
    timer: null,
    speed: 4,
  };
  PyMaster.viz = viz;

  PyMaster.openVisualizer = function (code, inputs) {
    var mask = document.getElementById('visualizer-modal');
    if (!mask) return;
    mask.hidden = false;
    document.getElementById('viz-code').innerHTML = '<div class="viz-empty">Processando…</div>';
    document.getElementById('viz-memory').innerHTML = '';
    document.getElementById('viz-console').innerHTML = '';
    var queue = inputs || [];
    if (queue.length > 50) return;
    fetch('/api/visualize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code, stdin: queue.join('\n') }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.input_request) {
          openInputModal(data.input_request.prompt || '', function (value) {
            if (value === '') return;
            PyMaster.openVisualizer(code, queue.concat([value]));
          });
          return;
        }
        viz.steps = data.steps || [];
        viz.idx = -1;
        if (!viz.steps.length) {
          document.getElementById('viz-code').innerHTML =
            '<div class="viz-error">' + esc(JSON.stringify(data.error)) + '</div>';
          return;
        }
        renderVizCode(code);
        viz.next();
      })
      .catch(function (e) {
        document.getElementById('viz-code').innerHTML = '<div class="viz-error">Falha: ' + esc(e.message) + '</div>';
      });
  };

  function renderVizCode(code) {
    var lines = code.split('\n');
    var html = [];
    lines.forEach(function (ln, i) {
      html.push('<div class="viz-line" data-line="' + (i + 1) + '"><span class="viz-line-no">' + (i + 1) + '</span><span class="viz-line-src">' + pyHighlight(ln) + '</span></div>');
    });
    document.getElementById('viz-code').innerHTML = html.join('\n');
  }

  function renderStep() {
    var step = viz.steps[viz.idx];
    if (!step) return;
    var lines = document.querySelectorAll('.viz-line');
    lines.forEach(function (l) { l.classList.remove('cur'); });
    var cur = document.querySelector('.viz-line[data-line="' + step.line + '"]');
    if (cur) cur.classList.add('cur');

    var mem = document.getElementById('viz-memory');
    var keys = Object.keys(step.variables || {});
    if (!keys.length) {
      mem.innerHTML = '<div class="viz-empty">(sem variáveis ainda)</div>';
    } else {
      var out = [];
      keys.forEach(function (name) {
        out.push('<div class="mem-box"><span class="mem-k">' + esc(name) + '</span><span class="mem-v">' + esc(step.variables[name]) + '</span></div>');
      });
      mem.innerHTML = out.join('');
    }
    document.getElementById('viz-step').textContent = 'Passo ' + (viz.idx + 1) + ' / ' + viz.steps.length;
  }

  viz.next = function () {
    if (viz.idx < viz.steps.length - 1) {
      viz.idx++;
      renderStep();
      if (viz.idx === viz.steps.length - 1 && viz.timer) viz.stopAuto();
    }
  };
  viz.prev = function () {
    if (viz.idx > 0) {
      viz.idx--;
      renderStep();
    }
  };
  viz.toggle = function () {
    if (viz.timer) viz.stopAuto();
    else viz.startAuto();
  };
  viz.startAuto = function () {
    var play = document.getElementById('viz-play');
    if (play) play.textContent = '⏸';
    viz.timer = setInterval(function () {
      if (viz.idx >= viz.steps.length - 1) { viz.stopAuto(); return; }
      viz.next();
    }, Math.max(150, 1500 / viz.speed));
  };
  viz.stopAuto = function () {
    if (viz.timer) { clearInterval(viz.timer); viz.timer = null; }
    var play = document.getElementById('viz-play');
    if (play) play.textContent = '▶';
  };

  document.addEventListener('DOMContentLoaded', function () {
    var speed = document.getElementById('viz-speed');
    if (speed) speed.addEventListener('input', function () { viz.speed = +speed.value; });
  });

  /* ─────────────────────── lab page ────────────────────────────── */
  function labCode() {
    var ta = document.getElementById('lab-code');
    return ta ? ta.value : '';
  }
  function renderLabConsole(d) {
      var wrap = document.getElementById('lab-console');
      var cls = d.ok ? '' : 'console-err';
      wrap.innerHTML =
        '<div class="lab-console ' + cls + '"><div class="console-head"><span class="' + (d.ok ? 'console-ok' : 'console-err-head') + '">' + (d.timeout ? '⏱ Interrompido' : d.ok ? '✓ Executado' : '✗ Erro') + '</span><span class="console-time">' + d.elapsed_ms + 'ms</span></div>'
        + '<pre class="console-output">' + esc(d.output) + '</pre>'
        + (d.error ? '<div class="console-error"><b>' + esc(d.error.class) + ':</b> ' + esc(d.error.message) + (d.error.line ? ' (linha ' + d.error.line + ')' : '') + '</div>' : '')
        + '</div>';
    }
    function runLab(code, inputs) {
      if (inputs.length > 50) return;
      fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code, stdin: inputs.join('\n') }),
      }).then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.input_request) {
            openInputModal(d.input_request.prompt || '', function (value) {
              if (value === '') return;
              inputs.push(value);
              runLab(code, inputs);
            });
            return;
          }
          renderLabConsole(d);
        })
        .catch(function (e) {
          document.getElementById('lab-console').innerHTML = '<div class="lab-console console-err">Falha de execução: ' + esc(e.message) + '</div>';
        });
    }
    function initLab() {
    var run = document.getElementById('lab-run');
    var vizBtn = document.getElementById('lab-visualize');
    var saveBtn = document.getElementById('lab-save');
    var clearBtn = document.getElementById('lab-clear');
    if (run) run.addEventListener('click', function () {
      var ta = document.getElementById('lab-code');
      if (!ta.value.trim()) { ta.value = 'print("Olá, PyMaster!")'; initEditor('lab-code', ta); }
      runLab(ta.value, []);
    });
    if (vizBtn) vizBtn.addEventListener('click', function () { PyMaster.openVisualizer(labCode()); });
    if (saveBtn) saveBtn.addEventListener('click', function () {
      var title = (document.getElementById('lab-title') || {}).value || 'Experimento';
      postForm('/frag/lab/save', { code: labCode(), title: title }).then(function (r) { return r.text(); })
        .then(function (html) {
          var list = document.getElementById('lab-history-list');
          if (list) list.innerHTML = html;
        });
    });
    if (clearBtn) clearBtn.addEventListener('click', function () {
      var ta = document.getElementById('lab-code');
      ta.value = '';
      initEditor('lab-code', ta);
    });
  }

  PyMaster.loadSample = function (name) {
    var ta = document.getElementById('lab-code');
    var samples = {
      loop: 'total = 0\nfor numero in range(1, 6):\n    total = total + numero\nprint(f"Soma: {total}")',
      func: 'def dobro(x):\n    return x * 2\n\nfor n in [1, 2, 3, 4]:\n    print(f"{n} → {dobro(n)}")',
      pandas: 'import pandas as pd\n\nvendas = pd.DataFrame({\n    \"produto\": [\"Caderno\", \"Caneta\", \"Mochila\"],\n    \"preco\": [15.90, 3.50, 89.90],\n    \"quantidade\": [5, 10, 2],\n})\n\nvendas[\"total\"] = vendas[\"preco\"] * vendas[\"quantidade\"]\nprint(vendas)\nprint(f\"\\nFaturamento: R$ {vendas[\'total\'].sum():,.2f}\")',
    };
    ta.value = samples[name] || '';
    initEditor('lab-code', ta);
    ta.focus();
  };

  PyMaster.loadSnippet = function (row) {
    var ta = document.getElementById('lab-code');
    if (ta) { ta.value = row.getAttribute('data-code') || ''; initEditor('lab-code', ta); }
  };

  document.addEventListener('click', function (e) {
    var btn = e.target && e.target.closest ? e.target.closest('.dataset-copy') : null;
    if (!btn) return;
    e.preventDefault();
    var name = btn.getAttribute('data-dataset') || '';
    var path = 'DATASETS_DIR + "/' + name + '"';
    function copied() {
      var old = btn.textContent;
      btn.textContent = '\u2713';
      btn.classList.add('copied');
      setTimeout(function () {
        btn.textContent = old;
        btn.classList.remove('copied');
      }, 1500);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(path).then(copied).catch(copied);
    } else {
      var ta = document.createElement('textarea');
      ta.value = path;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch (err) {}
      document.body.removeChild(ta);
      copied();
    }
  });
})();