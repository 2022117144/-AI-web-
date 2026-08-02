// ============================================================
// 智创工具 — 前端交互逻辑
// ============================================================
const API = "http://" + location.host + "/api";

// ========== 状态 ==========
let state = {
  projects: [],
  currentProject: null,
  styles: [],
  tasks: [],
  tab: "script",
  pipelineSteps: [],
  pipelineRuns: [],
  prompts: [],
  currentShots: [],
  selectedShotIdx: null,
  lastRunId: null,
  // 每个分镜的生成状态 { [idx]: { first: bool, last: bool } }
  // 初始化时先留空，切换项目时从 localStorage 恢复
  shotGenerating: {},
  // 分镜图片/视频数据缓存（直接从后端加载，不走 localStorage）
  shotDataCache: {},
};

// ========== 初始化 ==========
document.addEventListener("DOMContentLoaded", async () => {
  await loadStyles();
  await loadProjects();
  await loadPipelineSteps();
  await loadPrompts();
  checkStatus();
  // 恢复上次的文案
    const saved = localStorage.getItem(_projectKey("zctools_script"));
    if (saved) document.getElementById("storyInput").value = saved;
    // 自动保存文案到 localStorage（也自动存到项目）+ 实时字数统计
          document.getElementById("storyInput").addEventListener("input", function() {
            localStorage.setItem(_projectKey("zctools_script"), this.value);
            updateCharCount();
            // 自动保存到后端（防抖）
            clearTimeout(this._saveTimer);
            this._saveTimer = setTimeout(() => {
              if (state.currentProject && this.value.trim()) {
                saveProjectContent();
              }
            }, 1500);
          });
      // 初始化字数统计
      updateCharCount();
    // 初始化宫格
    changeGridSize();
    // 从 localStorage 恢复上次选中的项目，然后加载分镜数据
          const savedPid = localStorage.getItem("zctools_selected_project");
          if (savedPid) {
            const sel = document.getElementById("projectSelector");
            sel.value = savedPid;
            switchProject(savedPid);
          }
      // 检测是否有未完成的异步任务（分析/生成/修改），继续轮询
                        setTimeout(async () => {
                          const pid = savedPid;
                          const taskKeys = [
                            "zctools_task_analyze_",
                            "zctools_task_generate_",
                            "zctools_task_modify_",
                          ];
                          for (const key of taskKeys) {
                            const taskId = localStorage.getItem(key + pid);
                            if (taskId) {
                              // 直接继续轮询，不重试
                              const taskKey = key + pid;
                              try {
                                const resp = await api("/script/task/" + taskId);
                                if (resp.status === "running") {
                                                                  // 任务还在跑，显示状态并继续轮询等结果
                                                                  _setButtonStatus(key, true);
                                                                  _pollTask(taskId, taskKey).then(result => {
                                                                                                      _setButtonStatus(key, false);
                                                                                                      if (key === "zctools_task_analyze_") _handleAnalyzeResult(result);
                                                                                                      else if (key === "zctools_task_generate_") _handleGenerateResult(result);
                                                                                                      else if (key === "zctools_task_modify_") _handleModifyResult(result);
                                                                                                    }).catch(e => {
                                                                                                      _setButtonStatus(key, false);
                                                                                                      alert("任务恢复失败: " + e.message);
                                  });
                                } else if (resp.status === "completed") {
                                                                  // 任务已完成但前端没拿到结果，直接处理
                                                                  localStorage.removeItem(taskKey);
                                                                  _setButtonStatus(key, false);
                                                                  if (key === "zctools_task_analyze_") _handleAnalyzeResult(resp.result);
                                  else if (key === "zctools_task_generate_") _handleGenerateResult(resp.result);
                                  else if (key === "zctools_task_modify_") _handleModifyResult(resp.result);
                                } else {
                                  localStorage.removeItem(taskKey);
                                }
                              } catch {
                                localStorage.removeItem(taskKey);
                              }
                              break; // 一次只恢复一个任务
                            }
                          }
                        }, 500);
  // 恢复上次的 Tab（刷新后保持）— 优先 URL 参数
      const urlParams = new URLSearchParams(window.location.search);
      const urlTab = urlParams.get('tab');
      if (urlTab && ["script","shots","voiceover","pipeline","aitools","settings"].includes(urlTab)) {
              switchTab(urlTab);
            } else {
              const savedTab = localStorage.getItem("zctools_active_tab");
              if (savedTab && ["script","shots","voiceover","pipeline","aitools","settings"].includes(savedTab)) {
          switchTab(savedTab);
        } else {
          switchTab("script");
        }
      }
    // 如果 URL 有 project_id，自动选中项目
        const urlPid = urlParams.get('project_id');
        if (urlPid) {
          const sel = document.getElementById("projectSelector");
          // 直接尝试选中
          sel.value = urlPid;
          if (sel.value === urlPid) {
            // 选项存在，直接切换
            switchProject(urlPid);
          } else {
            // 选项不存在（API 失败等原因），从 localStorage 恢复
            var savedName = localStorage.getItem('wx_selected_project_name');
            if (savedName) {
              var opt = document.createElement('option');
              opt.value = urlPid;
              opt.textContent = savedName;
              sel.appendChild(opt);
              sel.value = urlPid;
              switchProject(urlPid);
            }
          }
        }
  // 修复浏览器自动填充问题
  const mi = document.getElementById("modifyInstruction");
  if (mi) mi.value = "";
});

// ========== API 工具 ==========
async function api(path, opts = {}) {
  const url = API + path;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    method: opts.method || (opts.body ? "POST" : "GET"),
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
    return res.json();
  }

  // ========== 异步任务轮询 ==========
  async function _pollTask(taskId, taskKey, maxWait = 300) {
    // 轮询任务状态，maxWait 秒超时
    const start = Date.now();
    while (true) {
      const resp = await api("/script/task/" + taskId);
      if (resp.status === "completed") {
        localStorage.removeItem(taskKey);
        return resp.result;
      }
      if (resp.status === "error") {
        localStorage.removeItem(taskKey);
        throw new Error(resp.error || "任务失败");
      }
      if ((Date.now() - start) > maxWait * 1000) {
        // 超时不删除 taskKey，刷新后继续轮询
        throw new Error("任务超时，请刷新页面继续等待");
      }
      await new Promise(r => setTimeout(r, 2000));
    }
  }

// ========== 按钮状态控制 ==========
function _setButtonStatus(key, loading) {
  const map = {
    "zctools_task_analyze_":   { id: "analyzeBtn",   text: "⏳ 分析中..." },
    "zctools_task_generate_":  { id: "genScriptBtn", text: "⏳ 生成中..." },
    "zctools_task_modify_":    { id: "modifyBtn",    text: "⏳ 修改中..." },
  };
  const cfg = map[key];
  if (!cfg) return;
  const btn = document.getElementById(cfg.id);
  if (!btn) return;
  btn.disabled = loading;
  btn.textContent = loading ? cfg.text : (cfg.id === "analyzeBtn" ? "🔍 分析文案生成" : cfg.id === "genScriptBtn" ? "✨ AI 生成" : "✨ AI 修改");
}


  // ========== 恢复未完成的任务 ==========
async function _resumePendingTask(pid) {
  if (!pid) return;
  const taskKeys = [
    "zctools_task_analyze_",
    "zctools_task_generate_",
    "zctools_task_modify_",
  ];
  for (const key of taskKeys) {
    const taskId = localStorage.getItem(key + pid);
    if (!taskId) continue;
    try {
      const resp = await api("/script/task/" + taskId);
      if (resp.status === "running") {
        _setButtonStatus(key, true);
        _pollTask(taskId, key + pid).then(result => {
          _setButtonStatus(key, false);
          if (key === "zctools_task_analyze_") _handleAnalyzeResult(result);
          else if (key === "zctools_task_generate_") _handleGenerateResult(result);
          else if (key === "zctools_task_modify_") _handleModifyResult(result);
        }).catch(e => {
          _setButtonStatus(key, false);
          alert("任务恢复失败: " + e.message);
        });
      } else if (resp.status === "completed") {
        localStorage.removeItem(key + pid);
        if (key === "zctools_task_analyze_") _handleAnalyzeResult(resp.result);
        else if (key === "zctools_task_generate_") _handleGenerateResult(resp.result);
        else if (key === "zctools_task_modify_") _handleModifyResult(resp.result);
      } else {
        localStorage.removeItem(key + pid);
      }
    } catch {
      localStorage.removeItem(key + pid);
    }
    break;
  }
}

// ========== 健康检查 ==========
async function checkStatus() {
  try {
    const h = await api("/health");
    document.getElementById("statusDot").className = "status-dot online";
    document.getElementById("statusText").textContent = `就绪 · ${h.builtin_styles} 风格`;
  } catch {
    document.getElementById("statusDot").className = "status-dot offline";
    document.getElementById("statusText").textContent = "后端未连接";
  }
}

// ========== 风格预设 ==========
async function loadStyles() {
  state.styles = await api("/styles");
  const sel = document.getElementById("styleSelector");
  sel.innerHTML = '<option value="">— 选择风格 —</option>';
  state.styles.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = s.name;
    sel.appendChild(opt);
  });
}

function onStyleChange() {
  const id = document.getElementById("styleSelector").value;
  const style = state.styles.find((s) => s.id === id);
  selectedVisualStyle = style || null;
  document.getElementById("styleAnchorText").textContent = style ? style.video_anchor : "（未选择）";
  document.getElementById("charAnchorText").textContent = style ? style.character_anchor : "（未选择）";
}

// 视频模型切换
function getVideoModel() {
  var sel = document.getElementById("videoModelSelect");
  if (sel && sel.value) return sel.value;
  var saved = localStorage.getItem("zctools_video_model");
  return saved || "Seedance-2.0-Mini";
}
function onVideoModelChange() {
  const sel = document.getElementById("videoModelSelect");
  if (!sel) return;
  localStorage.setItem("zctools_video_model", sel.value);
}

function restoreVideoModel() {
  var sel = document.getElementById("videoModelSelect");
  if (!sel) return;
  var saved = localStorage.getItem("zctools_video_model");
  if (saved) sel.value = saved;
}

// ========== 项目内容持久化 ==========
async function saveProjectContent() {
  if (!state.currentProject) return;
  const script = document.getElementById("storyInput").value;
  let shots = [];
  try { shots = JSON.parse(localStorage.getItem(_projectKey("zctools_shots_data")) || "[]"); } catch {}
  let srt = [];
  try { srt = JSON.parse(localStorage.getItem(_projectKey("zctools_srt")) || "[]"); } catch {}
  let shotData = {};
    try { shotData = JSON.parse(localStorage.getItem(_shotDataKey()) || "{}"); } catch {}
  const body = {};
  if (script) body.script_text = script;
  if (shots.length > 0) body.shots = shots;
  if (srt.length > 0) body.srt = srt;
  if (Object.keys(shotData).length > 0) body.shot_data = shotData;
  const gridSize = parseInt(document.getElementById("gridSizeSelect")?.value);
  if (gridSize) body.grid_size = gridSize;
  await api("/projects/" + state.currentProject.project_id + "/content", {
    method: "PUT",
    body: body,
  });
}

async function loadProjectContent(projectId, clearIfEmpty = false) {
  // 恢复该项目的生成中状态和选中分镜
  const genKey = "zctools_shot_generating_" + projectId;
  state.shotGenerating = JSON.parse(localStorage.getItem(genKey) || "{}");
  let hasData = false;
  try {
    const content = await api("/projects/" + projectId + "/content");
    // 恢复文案
        if (content.script_text) {
          document.getElementById("storyInput").value = content.script_text;
          localStorage.setItem(_projectKey("zctools_script"), content.script_text);
          hasData = true;
        } else {
          // 新项目没有文案，清空输入框
          document.getElementById("storyInput").value = "";
          localStorage.removeItem(_projectKey("zctools_script"));
        }
    // 恢复分镜
    if (content.shots && content.shots.length > 0) {
      localStorage.setItem(_projectKey("zctools_shots"), JSON.stringify(content.shots));
            localStorage.setItem(_projectKey("zctools_shots_data"), JSON.stringify(content.shots));
      state.currentShots = content.shots;
      renderShots(content.shots);
      const imgSection = document.getElementById("shotsImagesSection");
      if (imgSection) imgSection.style.display = "block";
      hasData = true;
    }
    // 恢复 SRT
    if (content.srt && content.srt.length > 0) {
      localStorage.setItem(_projectKey("zctools_srt"), JSON.stringify(content.srt));
      renderSRT(content.srt);
      hasData = true;
    }
    // 恢复分镜图片/视频数据（直接缓存到 state，不走 localStorage）
            if (content.shot_data && Object.keys(content.shot_data).length > 0) {
                  state.shotDataCache = content.shot_data;
              hasData = true;
            }
        // 恢复宫格尺寸
            if (content.grid_size && document.getElementById("gridSizeSelect")) {
              document.getElementById("gridSizeSelect").value = content.grid_size;
            }
            // 重新选中之前的分镜，如果不可用则默认选中第一个
                            if (content.shots && content.shots.length > 0) {
                              const savedShotIdx = parseInt(localStorage.getItem("zctools_selected_shot_" + projectId));
                              const targetIdx = (savedShotIdx >= 0 && savedShotIdx < content.shots.length) ? savedShotIdx : 0;
                              selectShot(targetIdx);
                              changeGridSize(targetIdx);
                            } else if (content.shot_data && Object.keys(content.shot_data).length > 0) {
                              // 没有分镜列表但有图片数据，选中第一个有图片的分镜
                              const savedShotIdx = parseInt(localStorage.getItem("zctools_selected_shot_" + projectId));
                              const keys = Object.keys(content.shot_data).map(Number).filter(k => !isNaN(k)).sort();
                              const targetIdx = keys.includes(savedShotIdx) ? savedShotIdx : (keys[0] || 0);
                              selectShot(targetIdx);
                              changeGridSize(targetIdx);
                            }
        // 清理该项目没有的数据（文案之外的数据，切换项目时用）
        if (clearIfEmpty) {
          if (!content.shots || content.shots.length === 0) {
            localStorage.removeItem(_projectKey("zctools_shots"));
                        localStorage.removeItem(_projectKey("zctools_shots_data"));
            state.currentShots = [];
            const grid = document.getElementById("shotsGrid");
            if (grid) grid.innerHTML = '<div class="shots-placeholder">未生成分镜</div>';
            document.getElementById("shotDetailPanel").style.display = "none";
          }
          if (!content.srt || content.srt.length === 0) {
            localStorage.removeItem(_projectKey("zctools_srt"));
            const srtEl = document.getElementById("srtOutput");
            if (srtEl) srtEl.value = "（未生成字幕）";
          }
          if (!content.shot_data || Object.keys(content.shot_data).length === 0) {
                      localStorage.removeItem(_shotDataKey());
          }
        }
        // 如果后端没数据且 clearIfEmpty=true，清空界面（切换项目时）
        if (!hasData && clearIfEmpty) {
          clearProjectContent();
        }
  } catch (e) {
    console.warn("加载项目内容失败:", e.message);
  }
}

function clearProjectContent() {
  document.getElementById("storyInput").value = "";
  localStorage.removeItem(_projectKey("zctools_script"));
    localStorage.removeItem(_projectKey("zctools_shots"));
    localStorage.removeItem(_projectKey("zctools_shots_data"));
    localStorage.removeItem(_projectKey("zctools_srt"));
    localStorage.removeItem(_shotDataKey());
  state.currentShots = [];
  const grid = document.getElementById("shotsGrid");
  if (grid) grid.innerHTML = '<div class="shots-placeholder">未生成分镜</div>';
  document.getElementById("shotDetailPanel").style.display = "none";
  const srtEl = document.getElementById("srtOutput");
  if (srtEl) srtEl.value = "（未生成字幕）";
}

// ========== 项目 ==========
async function loadProjects() {
  try {
    state.projects = await api("/projects");
  } catch {
    state.projects = [];
  }
  const sel = document.getElementById("projectSelector");
  sel.innerHTML = '<option value="">— 选择项目 —</option>';
  state.projects.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.project_id;
    opt.textContent = p.project_name + " (" + p.project_id.slice(0, 10) + "…)";
    sel.appendChild(opt);
  });
}

async function switchProject(id) {
  // 保存选中的项目 ID（刷新后恢复用）
  localStorage.setItem("zctools_selected_project", id || "");
  // 先保存当前项目内容
  if (state.currentProject) {
    await saveProjectContent();
  }
  state.currentProject = state.projects.find((p) => p.project_id === id) || null;
  // 如果 projects 列表为空（API 失败），直接用 ID 构造临时项目对象
  if (!state.currentProject && id) {
    state.currentProject = { project_id: id, project_name: '当前项目' };
  }
  if (state.currentProject) {
      await loadProjectContent(id, true);
    } else {
              clearProjectContent();
            }
            // 同步所有项目选择器
                        const sel = document.getElementById("projectSelector");
                        if (sel) sel.value = id || "";
                        const ps = document.getElementById("psChars");
                        if (ps) ps.value = id || "";
                        const pss = document.getElementById("psSettings");
                        if (pss) pss.value = id || "";
            // 切换项目后重置流水线显示
    resetPipelineDisplay();
        await loadPipelineRuns();
        await loadCharacters();
        await loadScenes();
  // 如果该项目有正在执行的流水线，显示其当前状态
    const runningRun = state.pipelineRuns.find((r) => r.status === "running");
    if (runningRun) {
      updatePipelineRunStatus(runningRun);
    }
    // 检测是否有未完成的异步任务（切换项目后恢复）
    _resumePendingTask(id);
}

function showNewProjectModal() {
  document.getElementById("newProjectModal").classList.add("show");
  document.getElementById("newProjectName").value = "";
  setTimeout(() => document.getElementById("newProjectName").focus(), 100);
}

async function createProject() {
  const name = document.getElementById("newProjectName").value.trim();
  if (!name) return;
  await api("/projects", { body: { project_name: name } });
  closeModal("newProjectModal");
  await loadProjects();
  // 自动选中新建的项目
  const proj = state.projects.find((p) => p.project_name === name);
  if (proj) {
    document.getElementById("projectSelector").value = proj.project_id;
    await switchProject(proj.project_id);
  }
}

async function deleteCurrentProject() {
  if (!state.currentProject) return;
  if (!confirm(`删除项目「${state.currentProject.project_name}」？`)) return;
  await api("/projects/" + state.currentProject.project_id, { method: "DELETE" });
  state.currentProject = null;
  document.getElementById("projectSelector").value = "";
  document.getElementById("storyInput").value = "";
  document.getElementById("voiceoverInput").value = "";
  await loadProjects();
}

function closeModal(id) {
  document.getElementById(id).classList.remove("show");
}

// 检查是否已选择项目
function requireProject() {
  if (!state.currentProject) {
    alert("请先选择项目");
    return false;
  }
  return true;
}

// ========== Tab 切换 ==========
function switchTab(name) {
  state.tab = name;
  localStorage.setItem("zctools_active_tab", name);
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".tab-content").forEach((c) => c.classList.toggle("active", c.id === "tab-" + name));
  if (name === "pipeline") loadPipelineRuns();
    if (name === "aitools") { loadCharacters(); loadScenes(); loadProps(); }
        if (name === "settings") { loadLLMConfig(); restoreVideoModel(); }
        if (name === "script") loadPrompts();
}

// ========== 分镜分析 + SRT ==========
async function analyzeScript() {
  if (!requireProject()) return;
  let script = document.getElementById("storyInput").value.trim();
  if (!script) {
    script = localStorage.getItem(_projectKey("zctools_script")) || "";
    if (script) {
      document.getElementById("storyInput").value = script;
    } else {
      alert("请先在文案 Tab 生成或输入文案");
      switchTab("script");
      return;
    }
  }

  const btn = document.getElementById("analyzeBtn");
  btn.disabled = true; btn.textContent = "⏳ 分析中...";

  try {
      // 创建异步任务
      var styleAnchor = "";
      if (selectedVisualStyle) {
        styleAnchor = selectedVisualStyle.video_anchor || "";
      }
      const task = await api("/script/task", { body: {
        type: "analyze",
        params: { topic: script, style_anchor: styleAnchor, project_id: state.currentProject ? state.currentProject.project_id : "" }
      }});
    const taskId = task.task_id;
    // 保存 task_id 到 localStorage，刷新后继续轮询
    const taskKey = "zctools_task_analyze_" + (state.currentProject ? state.currentProject.project_id : "_default");
    localStorage.setItem(taskKey, taskId);

    // 轮询任务结果
        const result = await _pollTask(taskId, taskKey);
        if (result && result.generated) {
          _handleAnalyzeResult(result);
        } else {
          alert("分析失败: " + (result?.error || "未知错误"));
        }
      } catch (e) { alert("分析失败: " + e.message); }
      finally { btn.disabled = false; btn.textContent = "🔍 分析文案生成"; }
    }

    function _handleAnalyzeResult(result) {
      renderShots(result.shots || []);
      renderSRT(result.srt || []);
      localStorage.setItem(_projectKey("zctools_shots"), JSON.stringify(result.shots || []));
      localStorage.setItem(_projectKey("zctools_srt"), JSON.stringify(result.srt || []));
      localStorage.setItem(_projectKey("zctools_shots_data"), JSON.stringify(result.shots || []));
      state.currentShots = result.shots || [];
      state.currentSRT = result.srt || [];
      const imgSection = document.getElementById("shotsImagesSection");
      if (imgSection) imgSection.style.display = "block";
      changeGridSize();
      if (state.currentProject) saveProjectContent();
      localStorage.removeItem("zctools_had_analysis_" + (state.currentProject ? state.currentProject.project_id : ""));
      markPipelineStep(2, "completed");
    }

function renderShots(shots) {
  const grid = document.getElementById("shotsGrid");
  if (!grid) return;
  if (!shots || shots.length === 0) {
    grid.innerHTML = '<div class="shots-placeholder">未生成分镜</div>';
    return;
  }
  // 保存到 state 和 localStorage
  state.currentShots = shots;
  localStorage.setItem(_projectKey("zctools_shots_data"), JSON.stringify(shots));
  grid.innerHTML = shots.map((s, i) => {
        // 首帧prompt：分镜1显示 first_frame_prompt，其他显示 last_frame_prompt（继承自上一分镜）
        let framePrompt = "";
        let frameFull = "";
        if (i === 0 && s.first_frame_prompt) {
        frameFull = s.first_frame_prompt;
        framePrompt = '<span class="frame-tag">首帧</span>' + (frameFull.length > 25 ? frameFull.slice(0, 25) + "..." : frameFull);
        }
        // 尾帧prompt：每个分镜都显示
        let lastPrompt = "";
        let lastFull = "";
        if (s.last_frame_prompt) {
        lastFull = s.last_frame_prompt;
        lastPrompt = '<span class="frame-tag">尾帧</span>' + (lastFull.length > 25 ? lastFull.slice(0, 25) + "..." : lastFull);
        }
        return `
                <div class="shot-card" data-idx="${i}" onclick="selectShot(${i})">
                  <div class="shot-num">${i + 1}</div>
                  <div class="shot-body">
                    <div class="shot-scene">${s.scene || s.prompt || ""}</div>
                    <div class="shot-prompt">${s.prompt ? "🎨 " + (s.prompt.length > 40 ? s.prompt.slice(0, 40) + "..." : s.prompt) : ""}</div>
                    ${framePrompt ? `<div class="shot-frame-prompt">${framePrompt}${frameFull.length > 25 ? `<span class="frame-view-btn" onclick="event.stopPropagation();showPromptPopup('首帧', '${escapeStr(frameFull)}', ${i}, 'first_frame_prompt')">查看全部</span>` : ""}</div>` : ""}
                                ${lastPrompt ? `<div class="shot-frame-prompt">${lastPrompt}${lastFull.length > 25 ? `<span class="frame-view-btn" onclick="event.stopPropagation();showPromptPopup('尾帧', '${escapeStr(lastFull)}', ${i}, 'last_frame_prompt')">查看全部</span>` : ""}</div>` : ""}
                                                                <div class="shot-duration">⏱ ${s.duration || 3}秒</div>
                                                  </div>
                                                </div>
                                              `;
      }).join("");
        // 选中之前的分镜，如果不可用则默认选中第一个
                const pid = state.currentProject ? state.currentProject.project_id : "_default";
                const savedShotIdx = parseInt(localStorage.getItem("zctools_selected_shot_" + pid));
                const targetIdx = (savedShotIdx >= 0 && savedShotIdx < shots.length) ? savedShotIdx : 0;
                selectShot(targetIdx);
      }

// 转义特殊字符，防止 HTML/JS 注入
function escapeStr(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/'/g, '\\x27').replace(/"/g, '&quot;');
}

// 可编辑提示词弹窗：显示完整 prompt 文本并支持修改保存
function showPromptPopup(type, text, shotIdx, fieldName) {
  // 移除已有的浮层
  var old = document.getElementById("promptPopup");
  if (old) old.remove();

  var popup = document.createElement("div");
  popup.id = "promptPopup";
  popup.className = "prompt-popup";

  var title = type + '完整提示词';
  var displayText = text || '';

  popup.innerHTML =
    '<div class="prompt-popup-header">' +
      '<span class="prompt-popup-title">' + title + '</span>' +
      '<span class="prompt-popup-close" onclick="closePromptPopup()">✕</span>' +
    '</div>' +
    '<div class="prompt-popup-body">' +
      '<textarea class="prompt-popup-editor" id="promptEditor">' + escapeStr(displayText) + '</textarea>' +
    '</div>' +
    '<div class="prompt-popup-footer">' +
      '<button class="btn btn-sm btn-outline" onclick="closePromptPopup()">取消</button>' +
      '<button class="btn btn-sm btn-primary" onclick="savePromptEdit(' + shotIdx + ',\'' + fieldName + '\')">💾 保存</button>' +
    '</div>';

  document.body.appendChild(popup);

  // 自动聚焦并选中文本
  setTimeout(function() {
    var editor = document.getElementById("promptEditor");
    if (editor) { editor.focus(); editor.select(); }
  }, 100);

  // 点击外部关闭
  setTimeout(function() {
    document.addEventListener("click", closePromptPopupOutside, false);
  }, 10);
}

function savePromptEdit(shotIdx, fieldName) {
  var editor = document.getElementById("promptEditor");
  if (!editor) return;
  var newText = editor.value.trim();

  // 更新 state
  if (state.currentShots && state.currentShots[shotIdx]) {
    state.currentShots[shotIdx][fieldName] = newText;
  }

  // 更新 localStorage
  var key = fieldName === 'first_frame_prompt' ? 'first_frame_prompt' : 'last_frame_prompt';
  try {
    var saved = JSON.parse(localStorage.getItem(_projectKey("zctools_shots_data")) || "[]");
        if (saved[shotIdx]) {
          saved[shotIdx][fieldName] = newText;
          localStorage.setItem(_projectKey("zctools_shots_data"), JSON.stringify(saved));
          localStorage.setItem(_projectKey("zctools_shots"), JSON.stringify(saved));
    }
  } catch(e) {}

  // 重新渲染分镜卡片
  renderShots(state.currentShots);

  // 重新选中当前分镜
  selectShot(shotIdx);

  // 保存到后端
  if (state.currentProject) saveProjectContent();

  closePromptPopup();
}

function closePromptPopup() {
  var popup = document.getElementById("promptPopup");
  if (popup) popup.remove();
  document.removeEventListener("click", closePromptPopupOutside, false);
}

function closePromptPopupOutside(e) {
  var popup = document.getElementById("promptPopup");
  if (popup && !popup.contains(e.target)) {
    closePromptPopup();
  }
}

  function renderSRT(srtList) {
  const srtEl = document.getElementById("srtOutput");
  if (!srtEl) return;
  if (!srtList || srtList.length === 0) { srtEl.value = "（未生成字幕）"; return; }
  srtEl.value = srtList.map((s, i) =>
    `${i + 1}\n${s.start || "00:00:00,000"} --> ${s.end || "00:00:03,000"}\n${s.text}\n`
  ).join("\n");
}

function changeGridSize(shotIdx) {
  const size = parseInt(document.getElementById("gridSizeSelect").value) || 9;
  const grid = document.getElementById("imageGrid");
  if (!grid) return;
  grid.setAttribute("data-size", size);
  const cols = Math.sqrt(size);
  grid.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
  grid.style.gridTemplateRows = `repeat(${cols}, 1fr)`;
  grid.innerHTML = "";

  // 如果指定了分镜索引，加载该分镜的图片
  const useIdx = (shotIdx !== undefined && shotIdx !== null) ? shotIdx : state.selectedShotIdx;
  let shotImages = [];
  if (useIdx !== null && useIdx !== undefined) {
    const sd = loadShotData(useIdx);
    if (sd.firstFrame || sd.firstFrameUploaded) shotImages.push({ src: sd.firstFrame || sd.firstFrameUploaded, label: "首帧" });
    if (sd.lastFrame || sd.lastFrameUploaded) shotImages.push({ src: sd.lastFrame || sd.lastFrameUploaded, label: "尾帧" });
  }

  for (let i = 0; i < size; i++) {
    const cell = document.createElement("div");
    cell.className = "grid-cell";
    cell.dataset.idx = i;
    if (i < shotImages.length && shotImages[i].src) {
      const src = shotImages[i].src;
      if (src.startsWith("data:")) {
        cell.innerHTML = `<img src="${src}" class="grid-cell-img" alt="${shotImages[i].label}"><div class="grid-cell-label">${shotImages[i].label}</div>`;
      } else if (src.startsWith("http")) {
        cell.innerHTML = `<img src="/api/image-proxy?url=${encodeURIComponent(src)}" class="grid-cell-img" alt="${shotImages[i].label}"><div class="grid-cell-label">${shotImages[i].label}</div>`;
      } else {
        cell.innerHTML = `<div class="grid-cell-placeholder">${i + 1}</div>`;
      }
    } else {
      cell.innerHTML = `<div class="grid-cell-placeholder">${i + 1}</div>`;
    }
    grid.appendChild(cell);
  }
}

function selectShot(idx) {
  // 更新卡片选中状态
  document.querySelectorAll(".shot-card").forEach((c) => c.classList.remove("selected"));
  const card = document.querySelector(`.shot-card[data-idx="${idx}"]`);
  if (card) card.classList.add("selected");

  state.selectedShotIdx = idx;
    // 持久化选中的分镜索引，按项目隔离
    const pid = state.currentProject ? state.currentProject.project_id : "_default";
    localStorage.setItem("zctools_selected_shot_" + pid, idx);
    const shot = state.currentShots && state.currentShots[idx];
    if (!shot) return;

    // 切换分镜时，根据该分镜的生成状态更新按钮
        const gen = state.shotGenerating[idx] || {};
        const firstBtn = document.getElementById("genFirstBtn");
        const lastBtn = document.getElementById("genLastBtn");
        if (gen.first) {
          firstBtn.disabled = true; firstBtn.textContent = "⏳";
        } else {
          firstBtn.disabled = false; firstBtn.textContent = "🖼";
        }
        if (gen.last) {
          lastBtn.disabled = true; lastBtn.textContent = "⏳";
        } else {
          lastBtn.disabled = false; lastBtn.textContent = "🖼";
        }

        // 从 localStorage 加载该分镜的图片/视频数据
  const shotData = loadShotData(idx);
  const prevShotData = idx > 0 ? loadShotData(idx - 1) : null;

  // 填充详情面板
  document.getElementById("shotDetailPanel").style.display = "block";
  document.getElementById("shotDetailTitle").textContent = `选卡 #${idx + 1}`;
  document.getElementById("shotDetailDuration").textContent = `${shot.duration || 3}秒`;
  document.getElementById("shotDetailScene").textContent = shot.scene || "";

  // === 首帧 ===
  const firstImg = document.getElementById("firstFrameImage");
  firstImg.dataset.shotIdx = idx;

  // 判断首帧来源：自己的 or 继承
    let ownFirstFrame = shotData.firstFrame || shotData.firstFrameUploaded;
    let isInherited = false;
    let inheritedUrl = "";

    if (!ownFirstFrame && idx > 0) {
      const prevData = loadShotData(idx - 1);
      const prevLast = prevData.lastFrame || prevData.lastFrameUploaded;
      if (prevLast) {
        isInherited = true;
        inheritedUrl = prevLast;
      }
    }

    const firstFrameSrc = ownFirstFrame || inheritedUrl;
            if (firstFrameSrc) {
              if (firstFrameSrc.startsWith("data:")) {
                firstImg.innerHTML = `<img src="${firstFrameSrc}" class="frame-img" alt="首帧">` + (isInherited ? '<div class="inherited-badge">⬆ 继承</div>' : '');
              } else if (firstFrameSrc.startsWith("http")) {
                firstImg.innerHTML = `<img src="/api/image-proxy?url=${encodeURIComponent(firstFrameSrc)}" class="frame-img" alt="首帧">` + (isInherited ? '<div class="inherited-badge">⬆ 继承</div>' : '');
              } else if (firstFrameSrc.startsWith("/api/")) {
                firstImg.innerHTML = `<img src="${firstFrameSrc}" class="frame-img" alt="首帧">` + (isInherited ? '<div class="inherited-badge">⬆ 继承</div>' : '');
              } else {
                firstImg.innerHTML = '<div class="frame-placeholder" style="display:flex;align-items:center;justify-content:center;height:100%">待生成</div>';
              }
        } else {
          // 检查是否正在生成中
          const gen = state.shotGenerating[idx] || {};
          if (gen.first) {
            firstImg.innerHTML = '<div class="frame-generating"><span class="gen-text">生成中...</span></div>';
          } else {
            firstImg.innerHTML = '<div class="frame-placeholder" style="display:flex;align-items:center;justify-content:center;height:100%">待生成</div>';
          }
        }

  // === 尾帧 ===
    const lastImg = document.getElementById("lastFrameImage");
    lastImg.dataset.shotIdx = idx;
    const ownLastFrame = shotData.lastFrame || shotData.lastFrameUploaded;
    if (ownLastFrame && ownLastFrame.startsWith("data:")) {
          lastImg.innerHTML = `<img src="${ownLastFrame}" class="frame-img" alt="尾帧">`;
        } else if (ownLastFrame && ownLastFrame.startsWith("http")) {
          lastImg.innerHTML = `<img src="/api/image-proxy?url=${encodeURIComponent(ownLastFrame)}" class="frame-img" alt="尾帧">`;
        } else if (ownLastFrame && ownLastFrame.startsWith("/api/")) {
          lastImg.innerHTML = `<img src="${ownLastFrame}" class="frame-img" alt="尾帧">`;
        } else if (ownLastFrame) {
      lastImg.innerHTML = '<div class="frame-placeholder" style="display:flex;align-items:center;justify-content:center;height:100%">待生成</div>';
    } else {
      // 检查是否正在生成中
      const gen = state.shotGenerating[idx] || {};
      if (gen.last) {
        lastImg.innerHTML = '<div class="frame-generating"><span class="gen-text">生成中...</span></div>';
      } else {
        lastImg.innerHTML = '<div class="frame-placeholder" style="display:flex;align-items:center;justify-content:center;height:100%">待生成</div>';
      }
    }

  // === 视频（预加载 + 缓存，切换不重新加载） ===
    const videoPreview = document.getElementById("shotVideoPreview");
    if (shotData.video) {
      const existing = videoPreview.querySelector("video");
      if (existing && existing.dataset.src === shotData.video) {
        // 同一个视频，不重新加载
      } else {
        videoPreview.innerHTML = `<video src="${shotData.video}" class="shot-video" controls data-src="${shotData.video}" preload="auto"></video>`;
      }
    } else {
      videoPreview.innerHTML = '<div class="frame-placeholder" style="display:flex;align-items:center;justify-content:center;height:100%">待生成</div>';
    }

  // 更新九宫格（显示当前分镜的图片）
  changeGridSize(idx);
}

// === 首帧/尾帧 上传 ===
function uploadFirstFrame() {
  document.getElementById("firstFrameUpload").click();
}
function uploadLastFrame() {
  document.getElementById("lastFrameUpload").click();
}
function handleFirstFrameUpload(e) {
  handleFrameUpload(e, "firstFrame");
}
function handleLastFrameUpload(e) {
  handleFrameUpload(e, "lastFrame");
}
function handleFrameUpload(e, type) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(ev) {
    const dataUrl = ev.target.result;
    const idx = parseInt(document.getElementById("firstFrameImage").dataset.shotIdx);
    if (type === "firstFrame") {
      saveShotData(idx, { firstFrameUploaded: dataUrl, firstFrame: "" });
    } else {
      saveShotData(idx, { lastFrameUploaded: dataUrl, lastFrame: "" });
    }
    selectShot(idx);
  };
  reader.readAsDataURL(file);
  e.target.value = "";
}

function _projectKey(prefix) {
  const pid = (state.currentProject && state.currentProject.project_id) || "_default";
  return prefix + "_" + pid;
}

function _shotDataKey() {
  // 按项目隔离 shot_data，避免切换项目时显示旧项目的图片
  const pid = (state.currentProject && state.currentProject.project_id) || "_default";
  return "zctools_shot_data_" + pid;
}

function loadShotData(idx) {
  try {
    // 优先从 state 缓存读（后端加载的数据），没有才走 localStorage
    const all = state.shotDataCache && Object.keys(state.shotDataCache).length > 0
      ? state.shotDataCache
      : JSON.parse(localStorage.getItem(_shotDataKey()) || "{}");
    const data = all[idx] || {};
    // 本地路径优先，没有才用 CDN URL
    if (data.firstFrameLocal) {
      // 绝对路径转为 /api/project-files/ 格式
      data.firstFrame = _toProjectFileUrl(data.firstFrameLocal);
    } else if (data.firstFrameUrl) {
      data.firstFrame = data.firstFrameUrl;
    }
    if (data.lastFrameLocal) {
      data.lastFrame = _toProjectFileUrl(data.lastFrameLocal);
    } else if (data.lastFrameUrl) {
      data.lastFrame = data.lastFrameUrl;
    }
    if (data.videoLocal) {
      data.video = _toProjectFileUrl(data.videoLocal);
    } else if (data.videoUrl) {
      data.video = data.videoUrl;
    }
    return data;
  } catch { return {}; }
}

function _toProjectFileUrl(localPath) {
  // 将本地绝对路径转为 /api/project-files/ 格式
  // 例: D:\万象AI改\zc_backend\data\project_content\proj_xxx\图片\xxx.jpg
  //   → /api/project-files/proj_xxx/图片/xxx.jpg
  // 也支持正斜杠格式: D:/万象AI改/.../project_content/proj_xxx/...
  const marker = "project_content\\";
  const idx = localPath.indexOf(marker);
  if (idx >= 0) {
    const rel = localPath.substring(idx + marker.length).replace(/\\/g, "/");
    return "/api/project-files/" + rel;
  }
  // 正斜杠版本
  const marker2 = "project_content/";
  const idx2 = localPath.indexOf(marker2);
  if (idx2 >= 0) {
    const rel = localPath.substring(idx2 + marker2.length);
    return "/api/project-files/" + rel;
  }
  // 如果已经是 /api/ 开头则直接返回
  if (localPath.startsWith("/api/")) return localPath;
  return localPath;
}

function saveShotData(idx, data) {
  try {
    const all = JSON.parse(localStorage.getItem(_shotDataKey()) || "{}");
    all[idx] = { ...(all[idx] || {}), ...data };
    localStorage.setItem(_shotDataKey(), JSON.stringify(all));
    // 自动保存到后端
    if (state.currentProject) {
      saveProjectContent();
    }
    // 检测是否有 CDN URL 需要下载到本地
    _downloadMediaToLocal(idx, data);
  } catch (e) {
    console.warn("saveShotData error:", e);
  }
}

async function _downloadMediaToLocal(idx, data) {
  if (!state.currentProject) return;
  const pid = state.currentProject.project_id;
  const fields = [
    { key: "firstFrame", type: "image" },
    { key: "lastFrame", type: "image" },
    { key: "video", type: "video" },
  ];
  for (const f of fields) {
    const url = data[f.key];
    if (!url || url.startsWith("data:") || url.startsWith("blob:")) continue;
    // 如果已经是 /api/project-files/ 本地路径，直接存为 xxxLocal 并同步到后端
    if (url.startsWith("/api/project-files/")) {
      const all = JSON.parse(localStorage.getItem(_shotDataKey()) || "{}");
      if (!all[idx]) all[idx] = {};
      // 从 /api/project-files/proj_xxx/图片/xxx.jpg 还原本地绝对路径
      const parts = url.replace("/api/project-files/", "").split("/");
      if (parts.length >= 3) {
        const localPath = "D:\\万象AI改\\zc_backend\\data\\project_content\\" + parts.join("\\");
        all[idx][f.key + "Local"] = localPath;
      }
      all[idx][f.key + "Url"] = url;
      localStorage.setItem(_shotDataKey(), JSON.stringify(all));
      if (state.currentProject) saveProjectContent();
      continue;
    }
    // 检查是否已下载过（本地路径以 /api/ 开头或 file: 开头则跳过）
    if (url.startsWith("/api/") || url.startsWith("file:")) continue;
    try {
      const res = await api("/projects/" + pid + "/download-media", {
        method: "POST",
        body: { url, type: f.type }
      });
      if (res.local_path) {
        // 更新 shot_data 中的路径为本地路径
        const all = JSON.parse(localStorage.getItem(_shotDataKey()) || "{}");
        if (!all[idx]) all[idx] = {};
        // 存本地路径，保留原始 URL 作为备用
        all[idx][f.key + "Local"] = res.local_path;
        all[idx][f.key + "Url"] = url;
        localStorage.setItem(_shotDataKey(), JSON.stringify(all));
        // 保存到后端
        if (state.currentProject) saveProjectContent();
      }
    } catch (e) {
      console.warn("下载媒体失败:", f.key, e.message);
    }
  }
}

// 将分镜的首帧/尾帧占位改为"生成中..."渲染效果
function setFrameGenerating(elId, idx) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.dataset.shotIdx = idx;
  el.innerHTML = '<div class="frame-generating"><span class="gen-text">生成中...</span></div>';
}

// 持久化生成中状态到 localStorage，按项目隔离
function persistShotGenerating() {
  const pid = state.currentProject ? state.currentProject.project_id : "_default";
  localStorage.setItem("zctools_shot_generating_" + pid, JSON.stringify(state.shotGenerating));
}

/**
 * 收集当前项目的角色和场景参考图 URL
 */
async function _getReferenceImages() {
  if (!state.currentProject) return [];
  const refs = [];
  try {
    const chars = await api("/characters?project_id=" + state.currentProject.project_id);
    for (const c of chars) {
      if (c.uploaded_image) refs.push(c.uploaded_image);
      if (c.three_view && c.three_view.images) refs.push(...c.three_view.images);
    }
    const scenes = await api("/scenes?project_id=" + state.currentProject.project_id);
    for (const s of scenes) {
      if (s.uploaded_image) refs.push(s.uploaded_image);
      if (s.generated_image) refs.push(s.generated_image);
    }
  } catch (e) { /* 静默失败，不影响主流程 */ }
  return refs;
}

async function genFirstFrame(idx) {
  if (!requireProject()) return;
  if (idx === undefined) idx = state.selectedShotIdx;
  if (idx === undefined || idx === null) { alert("请先选择一个分镜"); return; }
  const shot = state.currentShots && state.currentShots[idx];
  if (!shot) { alert("分镜数据不存在"); return; }

  // 如果该分镜正在生成中，不允许重复点击
    if (state.shotGenerating[idx] && state.shotGenerating[idx].first) return;

    // 首帧用 first_frame_prompt，降级到通用 prompt
    const prompt = shot.first_frame_prompt || shot.enhanced_prompt || shot.prompt || shot.scene || "";
    if (!prompt) { alert("该分镜无 prompt"); return; }

    // 标记该分镜首帧正在生成
    if (!state.shotGenerating[idx]) state.shotGenerating[idx] = {};
    state.shotGenerating[idx].first = true;
    // 仅非批量模式（有选中分镜且是当前分镜）时更新按钮
        const isSingle = idx === state.selectedShotIdx;
        let btn = null;
        if (isSingle) {
          btn = document.getElementById("genFirstBtn");
          btn.disabled = true; btn.textContent = "⏳";
        }
    // 占位文字改为"生成中..."
    setFrameGenerating("firstFrameImage", idx);
    persistShotGenerating();

  api("/generate-frame", {
              body: { prompt: prompt, aspect_ratio: "16:9", mode: "first_frame", project_id: state.currentProject ? state.currentProject.project_id : "", shot_idx: idx, reference_images: await _getReferenceImages() }
          }).then(res => {
                      if (window._batchCancelled) return;
                      if (res.success && res.image_url) {
                                saveShotData(idx, { firstFrame: res.image_url, firstFrameUploaded: "", firstFrameApiUrl: res.image_url });
                      // 直接渲染首帧图片
                      const firstImg = document.getElementById("firstFrameImage");
                      if (firstImg) {
                        firstImg.dataset.shotIdx = idx;
                        if (res.image_url.startsWith("data:")) {
                                                  firstImg.innerHTML = '<img src="' + res.image_url + '" class="frame-img" alt="首帧">';
                                                } else if (res.image_url.startsWith("/api/")) {
                                                  firstImg.innerHTML = '<img src="' + res.image_url + '" class="frame-img" alt="首帧">';
                                                } else {
                                                  firstImg.innerHTML = '<img src="/api/image-proxy?url=' + encodeURIComponent(res.image_url) + '" class="frame-img" alt="首帧">';
                                                }
                      }
                      selectShot(idx);
                                            if (isSingle) {
                                              btn.disabled = false; btn.textContent = "🖼";
                                            }
                                            // 保存到后端
                                            if (state.currentProject) saveProjectContent();
                                        } else {
                                          var errMsg = typeof res.error === 'string' ? res.error : JSON.stringify(res.error || "未知错误");
                                          alert("首帧生成失败: " + errMsg);
                                          if (isSingle) {
                                            btn.disabled = false; btn.textContent = "🖼";
                                          }
                                        }
                                        // 清除生成状态
                                                          if (state.shotGenerating[idx]) state.shotGenerating[idx].first = false;
                                                          persistShotGenerating();
                                                        }).catch(e => {
                                                                      if (window._batchCancelled) return;
                                                                      alert("首帧生成失败: " + e.message);
                                                  if (isSingle) {
                                                    btn.disabled = false; btn.textContent = "🖼";
                                                  }
                                                  if (state.shotGenerating[idx]) state.shotGenerating[idx].first = false;
                                                  persistShotGenerating();
                              });
                            }

                            async function genLastFrame(idx) {
                              if (!requireProject()) return;
                              if (idx === undefined) idx = state.selectedShotIdx;
                              if (idx === undefined || idx === null) { alert("请先选择一个分镜"); return; }
                              const shot = state.currentShots && state.currentShots[idx];
                              if (!shot) { alert("分镜数据不存在"); return; }

                              // 如果该分镜正在生成中，不允许重复点击
                                      if (state.shotGenerating[idx] && state.shotGenerating[idx].last) return;

                                      const prompt = shot.last_frame_prompt || shot.enhanced_prompt || shot.prompt || shot.scene || "";
                                      if (!prompt) { alert("该分镜无 prompt"); return; }

                                      // 标记该分镜尾帧正在生成
                                      if (!state.shotGenerating[idx]) state.shotGenerating[idx] = {};
                                      state.shotGenerating[idx].last = true;
                                      // 仅非批量模式时更新按钮
                                                                            const isSingle = idx === state.selectedShotIdx;
                                                                            let btn = null;
                                                                            if (isSingle) {
                                                                              btn = document.getElementById("genLastBtn");
                                                                              btn.disabled = true; btn.textContent = "⏳";
                                                                            }
                                      // 占位文字改为"生成中..."
                                                      setFrameGenerating("lastFrameImage", idx);
                                                      persistShotGenerating();

                        api("/generate-frame", {
                                                body: { prompt: prompt, aspect_ratio: "16:9", mode: "last_frame", project_id: state.currentProject ? state.currentProject.project_id : "", shot_idx: idx, reference_images: await _getReferenceImages() }
                      }).then(res => {
                                              if (window._batchCancelled) return;
                                              if (res.success && res.image_url) {
                                                saveShotData(idx, { lastFrame: res.image_url, lastFrameUploaded: "", lastFrameApiUrl: res.image_url });
                          // 直接渲染尾帧图片（不依赖 selectShot）
                          const lastImg = document.getElementById("lastFrameImage");
                          if (lastImg) {
                            lastImg.dataset.shotIdx = idx;
                            if (res.image_url.startsWith("data:")) {
                              lastImg.innerHTML = '<img src="' + res.image_url + '" class="frame-img" alt="尾帧">';
                            } else {
                              lastImg.innerHTML = '<img src="/api/image-proxy?url=' + encodeURIComponent(res.image_url) + '" class="frame-img" alt="尾帧">';
                            }
                          }
                          selectShot(idx);
                                                    if (isSingle) {
                                                      btn.disabled = false; btn.textContent = "🖼";
                                                    }
                                                    // 保存到后端
                                                    if (state.currentProject) saveProjectContent();
                                                  } else {
                                        alert("尾帧生成失败: " + (typeof res.error === 'string' ? res.error : JSON.stringify(res.error || "未知错误")));
                                        if (isSingle) {
                                          btn.disabled = false; btn.textContent = "🖼";
                                        }
                                      }
                                      // 清除生成状态
                                                  if (state.shotGenerating[idx]) state.shotGenerating[idx].last = false;
                                                  persistShotGenerating();
                                                }).catch(e => {
                                                                                                if (window._batchCancelled) return;
                                                                                                alert("尾帧生成失败: " + e.message);
                                                if (isSingle) {
                                                  btn.disabled = false; btn.textContent = "🖼";
                                                }
                      if (state.shotGenerating[idx]) state.shotGenerating[idx].last = false;
                      persistShotGenerating();
        });
      }

// ========== 批量生成所有分镜的首帧 + 尾帧（同步提交，一起等待） ==========
async function batchGenFrames() {
  if (!requireProject()) return;
  const shots = state.currentShots;
  if (!shots || shots.length === 0) { alert("没有分镜数据"); return; }

  window._batchCancelled = false;

  const btn = document.getElementById("batchGenBtn");
  btn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = "⏳ 提交中...";

  // 第一步：收集所有需要生成的请求（跳过已生成的）
  const tasks = [];
  for (let i = 0; i < shots.length; i++) {
    const shot = shots[i];
    const shotData = loadShotData(i);
    // 首帧（仅第一个分镜需要首帧）
        if (i === 0 && !shotData.firstFrame && !shotData.firstFrameUploaded) {
      const p = shot.first_frame_prompt || shot.enhanced_prompt || shot.prompt || shot.scene || "";
      if (p) tasks.push({ idx: i, type: "first", prompt: p });
    }
    // 尾帧
    if (!shotData.lastFrame && !shotData.lastFrameUploaded) {
      const p = shot.last_frame_prompt || shot.enhanced_prompt || shot.prompt || shot.scene || "";
      if (p) tasks.push({ idx: i, type: "last", prompt: p });
    }
  }

  if (tasks.length === 0) {
    alert("所有图片已生成，无需批量生成");
    btn.disabled = false;
    btn.textContent = originalText;
    return;
  }

  btn.textContent = `⏳ 批量提交 ${tasks.length} 张...`;

  // 更新占位文字为"生成中..."
    for (const t of tasks) {
      const elId = t.type === "first" ? "firstFrameImage" : "lastFrameImage";
      setFrameGenerating(elId, t.idx);
    }
  // 如果当前选中的分镜在任务列表里，更新按钮状态
  if (state.selectedShotIdx !== null) {
    const gen = state.shotGenerating[state.selectedShotIdx] || {};
    const firstBtn = document.getElementById("genFirstBtn");
    const lastBtn = document.getElementById("genLastBtn");
    if (gen.first) { firstBtn.disabled = true; firstBtn.textContent = "⏳"; }
    if (gen.last) { lastBtn.disabled = true; lastBtn.textContent = "⏳"; }
  }

  // 第二步：提交批量生成任务到后端
      btn.textContent = `⏳ 批量提交 ${tasks.length} 张...`;

      try {
        // 收集参考图
        const refs = await _getReferenceImages();

        // 提交批量任务
        const task = await api("/batch-generate-frames", { body: {
          project_id: state.currentProject ? state.currentProject.project_id : "",
          aspect_ratio: "16:9",
          frames: tasks.map(t => ({ prompt: t.prompt, mode: t.type === "first" ? "first_frame" : "last_frame", shot_idx: t.idx })),
          reference_images: refs,
        }});
        const taskId = task.task_id;
        btn.textContent = `⏳ 生成中 0/${task.total}...`;

        // 轮询任务结果
        let polled = 0;
        while (true) {
          await new Promise(r => setTimeout(r, 3000));
          const status = await api("/batch-generate-frames/" + taskId);
          if (status.status === "completed") {
            // 处理结果
            let success = 0, fail = 0;
            for (const r of status.results || []) {
              if (r.success) {
                success++;
                saveShotData(r.shot_idx, { [r.mode === "first_frame" ? "firstFrame" : "lastFrame"]: r.image_url, [r.mode === "first_frame" ? "firstFrameApiUrl" : "lastFrameApiUrl"]: r.image_url });
              } else {
                fail++;
              }
            }
            // 刷新显示
            if (state.selectedShotIdx !== null) selectShot(state.selectedShotIdx);
            if (state.currentProject) await saveProjectContent();
            btn.disabled = false;
            btn.textContent = originalText;
            window._batchCancelled = false;
            alert(`批量生成完成！成功 ${success} 张，失败 ${fail} 张`);
            return;
          } else if (status.status === "error") {
            throw new Error(status.error || "批量生成失败");
          }
          // 更新进度
          polled++;
          btn.textContent = `⏳ 生成中 ${polled * 3}秒...`;
        }
      } catch (e) {
        alert("批量生成失败: " + e.message);
        btn.disabled = false;
        btn.textContent = originalText;
        window._batchCancelled = false;
      }
    }

          /**
           * 一键暂停批量生成 — 释放 shotGenerating 锁，重置所有占位文字
           */
          function cancelBatchFrames() {
            window._batchCancelled = true;

            // 清空所有生成状态，释放锁
            for (const idx in state.shotGenerating) {
              state.shotGenerating[idx] = {};
            }
            persistShotGenerating();

            // 重置所有分镜的占位文字为"待生成"
            for (let i = 0; i < (state.currentShots || []).length; i++) {
              const firstImg = document.getElementById("firstFrameImage");
              if (firstImg && parseInt(firstImg.dataset.shotIdx) === i) {
                const gen = state.shotGenerating[i] || {};
                if (!gen.first) {
                  firstImg.innerHTML = '<div class="frame-placeholder" style="display:flex;align-items:center;justify-content:center;height:100%">待生成</div>';
                }
              }
              const lastImg = document.getElementById("lastFrameImage");
              if (lastImg && parseInt(lastImg.dataset.shotIdx) === i) {
                const gen = state.shotGenerating[i] || {};
                if (!gen.last) {
                  lastImg.innerHTML = '<div class="frame-placeholder" style="display:flex;align-items:center;justify-content:center;height:100%">待生成</div>';
                }
              }
            }

            // 释放按钮
            if (state.selectedShotIdx !== null) {
              const gen = state.shotGenerating[state.selectedShotIdx] || {};
              const firstBtn = document.getElementById("genFirstBtn");
              const lastBtn = document.getElementById("genLastBtn");
              if (!gen.first) { firstBtn.disabled = false; firstBtn.textContent = "🖼"; }
              if (!gen.last) { lastBtn.disabled = false; lastBtn.textContent = "🖼"; }
            }

            // 恢复批量生成按钮
            const batchBtn = document.getElementById("batchGenBtn");
                        batchBtn.disabled = false;
                        batchBtn.textContent = "🖼 批量生成所有图片";

                        alert("已暂停批量生成");
                      }

                      /**
                       * 一键生成所有分镜的视频 — 检查每个分镜是否都有首尾帧，有则生成视频
                       */
                      async function batchGenVideos() {
                                              if (!requireProject()) return;
                                              const shots = state.currentShots;
                                              if (!shots || shots.length === 0) { alert("没有分镜数据"); return; }

                                              // 检查每个分镜是否有首尾帧，并统计需要生成视频的分镜
                                                                      const missing = [];
                                                                      const tasks = [];
                                                                      for (let i = 0; i < shots.length; i++) {
                                                                        const shotData = loadShotData(i);
                                                                        // 跳过已有视频的分镜
                                                                        if (shotData && shotData.video) continue;
                                                                        const prevData = i > 0 ? loadShotData(i - 1) : null;
                                                                        const firstFrame = shotData.firstFrame || shotData.firstFrameUploaded ||
                                                                          (i > 0 ? (prevData.lastFrame || prevData.lastFrameUploaded) : null);
                                                                        const lastFrame = shotData.lastFrame || shotData.lastFrameUploaded;
                                                                        if (!firstFrame) missing.push({ idx: i, type: "首帧" });
                                                                        if (!lastFrame) missing.push({ idx: i, type: "尾帧" });
                                                                        tasks.push({ idx: i });
                                                                      }

                                                                      if (missing.length > 0) {
                                                                        const msg = missing.map(m => `#${m.idx + 1} ${m.type}`).join("、");
                                                                        if (!confirm(`以下分镜缺少首尾帧，将跳过这些分镜不生成视频：\n${msg}\n\n要继续为有首尾帧的分镜生成视频吗？`)) {
                                                                          return;
                                                                        }
                                                                        // 从 tasks 中移除缺帧的分镜（只保留有首帧+尾帧的）
                                                                        const validTasks = [];
                                                                        for (const t of tasks) {
                                                                          const sd = loadShotData(t.idx);
                                                                          const prevData = t.idx > 0 ? loadShotData(t.idx - 1) : null;
                                                                          const ff = sd.firstFrame || sd.firstFrameUploaded ||
                                                                            (t.idx > 0 ? (prevData.lastFrame || prevData.lastFrameUploaded) : null);
                                                                          const lf = sd.lastFrame || sd.lastFrameUploaded;
                                                                          if (ff && lf) validTasks.push(t);
                                                                        }
                                                                        tasks.length = 0;
                                                                        tasks.push(...validTasks);
                                                                        if (tasks.length === 0) { alert("所有分镜都缺少首尾帧，无法生成视频"); return; }
                                                                      }

                                                // 检查 insMind 可用账号数是否足够
                                                                        let availableAccounts = 0;
                                                                        try {
                                                                          const acctResp = await fetch("/api/insmind-accounts/count").then(r => r.json());
                                                                          availableAccounts = acctResp && acctResp.success ? acctResp.success : 0;
                                                                        } catch (e) {
                                                                          // 接口失败，默认允许（不阻塞）
                                                                          availableAccounts = 999;
                                                                        }
                                                const needed = tasks.length;
                                                                                                if (needed === 0) {
                                                                                                  alert("所有分镜已有视频，无需生成");
                                                                                                  return;
                                                                                                }
                                                                                                if (availableAccounts < needed) {
                                                                                                                                                  alert(`insMind 可用账号不足：需要 ${needed} 个账号，当前可用 ${availableAccounts} 个\n请先注册新账号或等待额度重置`);
                                                                                                                                                  throw new Error("insMind 可用账号不足");
                                                }

                                                const btn = document.getElementById("batchVideoBtn");
                                                                        btn.disabled = true;
                                                                        btn.textContent = "⏳ 生成中...";

                                                                        // 同步提交所有视频生成请求
                        const results = await Promise.allSettled(
                          tasks.map(t => new Promise(resolve => {
                            genShotVideo(t.idx);
                            // 轮询等待视频生成完成（shotData.video 有值）
                            const check = setInterval(() => {
                              const sd = loadShotData(t.idx);
                              if (sd && sd.video) {
                                clearInterval(check);
                                resolve({ status: "fulfilled" });
                              }
                            }, 500);
                            setTimeout(() => { clearInterval(check); resolve({ status: "fulfilled" }); }, 600000); // 10分钟超时
                          }))
                        );

                        let success = 0;
                        let fail = 0;
                        for (const r of results) {
                          if (r.status === "fulfilled") success++;
                          else fail++;
                        }

                        if (state.selectedShotIdx !== null) selectShot(state.selectedShotIdx);
                        if (state.currentProject) await saveProjectContent();

                        btn.disabled = false;
                        btn.textContent = "🎬 一键生成视频";
                        alert(`视频生成完成！成功 ${success} 个，失败 ${fail} 个`);
                      }

                      function genShotVideo(idx) {
            if (!requireProject()) return;
            if (idx === undefined) idx = state.selectedShotIdx;
            if (idx === undefined || idx === null) { alert("请先选择一个分镜"); return; }
  const shot = state.currentShots && state.currentShots[idx];
  if (!shot) { alert("分镜数据不存在"); return; }

  // 尾帧用 last_frame_prompt，降级到通用 prompt
  const prompt = shot.last_frame_prompt || shot.enhanced_prompt || shot.prompt || shot.scene || "";
  if (!prompt) { alert("该分镜无 prompt"); return; }

  const shotData = loadShotData(idx);
  const prevData = idx > 0 ? loadShotData(idx - 1) : null;

  // 计算实际首尾帧
  const firstFrame = shotData.firstFrame || shotData.firstFrameUploaded ||
    (idx > 0 ? (prevData.lastFrame || prevData.lastFrameUploaded) : null);
  const lastFrame = shotData.lastFrame || shotData.lastFrameUploaded;

    const isSingle = idx === state.selectedShotIdx;
    const btn = document.getElementById("genVideoBtn");
    if (isSingle) {
      btn.disabled = true; btn.textContent = "⏳ 生成中...";
    }

    api("/generate-video", {
      body: {
        prompt: prompt,
        first_frame: firstFrame || "",
        last_frame: lastFrame || "",
        model: getVideoModel(),
        ratio: "16:9",
        resolution: "360p",
        duration: shot.duration || 5,
        project_id: state.currentProject ? state.currentProject.project_id : "",
        shot_idx: idx,
      },
  }).then(res => {
        if (res.success && res.video_url) {
          saveShotData(idx, { video: res.video_url });
          selectShot(idx);
          if (isSingle) { btn.disabled = false; btn.textContent = "🎬 生成视频"; }
          // 保存到后端
          if (state.currentProject) saveProjectContent();
        } else {
        alert("视频生成失败: " + (typeof res.error === 'string' ? res.error : JSON.stringify(res.error || "未知错误")));
        if (isSingle) { btn.disabled = false; btn.textContent = "🎬 生成视频"; }
      }
    }).catch(e => {
      alert("视频生成失败: " + e.message);
      if (isSingle) { btn.disabled = false; btn.textContent = "🎬 生成视频"; }
  });
}

// 恢复状态
function restoreShotsFromStorage() {
  try {
    const data = localStorage.getItem(_projectKey("zctools_shots_data"));
    if (data) {
      state.currentShots = JSON.parse(data);
      renderShots(state.currentShots);
      const imgSection = document.getElementById("shotsImagesSection");
      if (imgSection && state.currentShots.length > 0) imgSection.style.display = "block";
    }
  } catch {}
}

// ========== 增强提示词 ==========
async function enhancePrompt() {
  const prompt = state.tab === "script"
    ? document.getElementById("storyInput").value
    : state.tab === "shots"
    ? getShotsText()
    : document.getElementById("voiceoverInput").value;

  if (!prompt.trim()) { alert("请先输入内容"); return; }

  const styleId = document.getElementById("styleSelector").value;
  try {
    const res = await api("/prompt/enhance", {
      body: { prompt, style_preset_id: styleId, mode: document.getElementById("modeSelect").value },
    });
    document.getElementById("enhancedPreview").textContent = res.enhanced_prompt;
  } catch (e) {
    document.getElementById("enhancedPreview").textContent = "增强失败: " + e.message;
  }
}

function getShotsText() {
  return [...document.querySelectorAll(".shot-input")]
    .map((inp, i) => `[镜头${i+1}] ${inp.value}`)
    .join("\n");
}

// ========== 生成视频 ==========
async function generateVideo() {
  if (!requireProject()) return;
  const enhanced = document.getElementById("enhancedPreview").textContent;
  if (enhanced.includes("选择一个风格预设") || !enhanced.trim()) {
    alert("请先增强提示词");
    return;
  }
  const task = { id: "task-" + Date.now(), name: "视频生成", type: "video", progress: 0, prompt: enhanced.slice(0, 40) + "…" };
  addTask(task);
  try {
    const res = await api("/generate", {
      body: {
        prompt: document.getElementById("storyInput").value || enhanced,
        enhanced_prompt: enhanced,
        task_type: document.getElementById("modeSelect").value,
        params: { aspect_ratio: document.getElementById("aspectRatio").value, duration: parseInt(document.getElementById("duration").value) },
      },
    });
    updateTask(task.id, 100, res.status === "completed" ? "完成" : res.status);
  } catch (e) {
    updateTask(task.id, 0, "失败: " + e.message);
  }
}

// ========== TTS ==========
async function genTTS() {
  if (!requireProject()) return;
  const task = { id: "tts-" + Date.now(), name: "语音生成", type: "tts", progress: 0 };
  addTask(task);
  try {
    const res = await api("/generate", {
      body: { prompt: "", enhanced_prompt: document.getElementById("voiceoverInput").value || "TTS", task_type: "tts", params: {} },
    });
    updateTask(task.id, 100, res.status === "completed" ? "完成" : res.status);
  } catch (e) {
    updateTask(task.id, 0, "失败: " + e.message);
  }
}

// ========== 任务队列 ==========
function addTask(task) { state.tasks.push(task); renderTasks(); }
function updateTask(id, progress, statusText) {
  const task = state.tasks.find((t) => t.id === id);
  if (task) { task.progress = progress; if (statusText) task.statusText = statusText; renderTasks(); }
}
function renderTasks() {
  const list = document.getElementById("taskList");
  if (state.tasks.length === 0) { list.innerHTML = '<div class="task-placeholder">暂无生成任务</div>'; return; }
  list.innerHTML = state.tasks.map((t) => `
    <div class="task-card">
      <div class="task-info"><span class="task-name">${t.name}</span><span class="task-prompt">${t.prompt || ""}</span></div>
      <div class="task-progress"><div class="progress-bar"><div class="progress-fill" style="width:${t.progress}%"></div></div><span class="progress-text">${Math.round(t.progress)}%</span></div>
    </div>`).join("");
}

// 标记流水线步骤完成（级联+持久化）
function markPipelineStep(stepIndex, status) {
  // 更新本地 state
  if (!state.pipelineRun) {
    state.pipelineRun = { steps: [], run_id: "run_" + Date.now().toString(36), project_id: state.currentProject || "" };
    for (var i = 0; i < 7; i++) state.pipelineRun.steps.push({ status: "pending" });
  }
  // 级联：完成第N步时，前面所有步骤也标记为完成
  if (status === "completed") {
    for (var j = 0; j <= stepIndex - 1; j++) {
      if (state.pipelineRun.steps[j]) state.pipelineRun.steps[j].status = "completed";
    }
  }
  if (state.pipelineRun.steps[stepIndex - 1]) {
    state.pipelineRun.steps[stepIndex - 1].status = status;
  }
  // 持久化到后端
  var runId = state.pipelineRun.run_id || "run_" + Date.now().toString(36);
  var projId = state.currentProject || "";
  fetch("/api/pipeline/runs/" + runId + "/step", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ step_index: stepIndex - 1, status: status, project_id: projId, run_id: runId })
  }).catch(function(e){ console.warn("保存流水线状态失败:", e); });
  // 重新渲染流水线
  renderPipelineFlow();
}

// ========== 流水线 (Pipeline) ==========

async function loadPipelineSteps() {
  try {
    state.pipelineSteps = await api("/pipeline/steps");
    // 加载当前项目的最新流水线运行状态
    if (state.currentProject) {
      try {
        var pid = typeof state.currentProject === "string" ? state.currentProject : (state.currentProject.project_id || "");
        var runs = await api("/pipeline/runs?project_id=" + pid);
        if (Array.isArray(runs) && runs.length > 0) {
          state.pipelineRun = runs[0];
        }
      } catch(e) { /* 忽略 */ }
    }
    renderPipelineFlow();
  } catch (e) { console.warn("流水线步骤加载失败:", e.message); }
}

function renderPipelineFlow() {
  const container = document.getElementById("pipelineFlow");
  if (!container || state.pipelineSteps.length === 0) {
    if (container) container.innerHTML = '<div class="pipeline-placeholder">加载步骤定义中...</div>';
    return;
  }
  container.innerHTML = `
      <div class="pipeline-title">📋 完整流水线</div>
      <div class="pipeline-steps">
        ${state.pipelineSteps.map((s, i) => {
          var stepStatus = "pending";
          if (state.pipelineRun && state.pipelineRun.steps && state.pipelineRun.steps[i]) {
            stepStatus = state.pipelineRun.steps[i].status;
          }
          var statusClass = stepStatus === "completed" ? "pipe-completed" : stepStatus === "running" ? "pipe-running" : stepStatus === "error" ? "pipe-error" : stepStatus === "skipped" ? "pipe-skipped" : "";
          return `
          <div class="pipe-step ${statusClass}" data-step="${s.name}">
            <div class="pipe-step-num">${i + 1}</div>
            <div class="pipe-step-body">
              <div class="pipe-step-name">${s.label}</div>
                          <div class="pipe-step-desc">${s.description}</div>
                        </div>
          </div>
          ${i < state.pipelineSteps.length - 1 ? '<div class="pipe-arrow">↓</div>' : ''}
        `}).join("")}
      </div>
    `;
}

function resetPipelineDisplay() {
  // 加载当前项目的最新流水线运行状态
  if (state.currentProject) {
    try {
      var xhr = new XMLHttpRequest();
      xhr.open("GET", "/api/pipeline/runs?project_id=" + state.currentProject.project_id, false);
      xhr.send();
      if (xhr.status === 200) {
        var runs = JSON.parse(xhr.responseText);
        if (Array.isArray(runs) && runs.length > 0) {
          state.pipelineRun = runs[0];
        }
      }
    } catch(e) { /* 忽略 */ }
  }
  // 重渲染流水线步骤（从步骤定义重建 DOM）
  renderPipelineFlow();
  // 清空执行记录列表
  const listEl = document.getElementById("pipelineRunList");
  if (listEl) listEl.innerHTML = '<div class="pipeline-placeholder">暂无执行记录</div>';
  // 重置右侧面板流水线状态
  const rightStatus = document.getElementById("rightPipelineStatus");
  if (rightStatus) {
    const labels = ["文案", "分镜+字幕+音频", "图片", "视频", "合成", "发送"];
        rightStatus.innerHTML = labels.map((l, i) =>
          `<div>步骤 ${i + 1}/6 · ${l} ⏳</div>`
        ).join("") + '<div style="color:var(--text-muted);margin-top:8px;font-size:10px">点击流水线 Tab 查看详情</div>';
  }
  // 清除轮询
  if (pipelinePollTimer) {
    clearInterval(pipelinePollTimer);
    pipelinePollTimer = null;
  }
}

async function runPipeline() {
  if (!requireProject()) return;
  const projectId = state.currentProject ? state.currentProject.project_id : "";
  if (!projectId) { alert("请先选择项目"); return; }

  const btn = document.getElementById("runPipelineBtn");
  const stopBtn = document.getElementById("stopPipelineBtn");
  btn.disabled = true;
  btn.style.display = "none";
  stopBtn.style.display = "inline-block";

  try {
      // 先检查当前项目各步骤完成状态
      const status = await api("/projects/" + projectId + "/pipeline-status");
            var steps = status.steps || [false, false, false, false, false, false];
            const stepLabels = ["文案", "分镜+字幕+音频", "图片", "视频", "合成", "发送"];

      // 找到第一个未完成的步骤
      var startFrom = steps.findIndex((s) => !s);
    if (startFrom === -1) {
      alert("所有步骤已完成！");
      syncPipelineButtons();
      return;
    }

    // 标记前面已完成的步骤
    for (let i = 0; i < startFrom; i++) {
      if (steps[i]) markPipelineStep(i + 1, "completed");
    }

    // 从第一个未完成的步骤开始执行
    for (let i = startFrom; i < 6; i++) {
      if (steps[i]) continue; // 已完成的跳过
      stopBtn.textContent = "⏹ 步骤" + (i + 1) + "/6 " + stepLabels[i] + "...";

      if (i === 0) {
              // 步骤1: 文案 — 检查输入框是否有文案
              const scriptText = document.getElementById("storyInput")?.value?.trim() || "";
              if (!scriptText) {
                throw new Error("请先输入文案内容");
              }
              markPipelineStep(1, "completed");
      } else if (i === 1) {
        // 步骤2: 分镜+字幕+音频 — 调用分析文案生成
        await analyzeScript();
        // analyzeScript 内部会调 markPipelineStep(2, "completed")
      } else if (i === 2) {
                    // 步骤3: 图片 — 调用批量生成图片
                    await batchGenFrames();
                    // 执行后重新检查图片是否足够
                    const status3 = await api("/projects/" + projectId + "/pipeline-status");
                    if (!status3.steps[2]) {
                      throw new Error("图片生成不足，无法继续下一步");
                    }
                    markPipelineStep(3, "completed");
      } else if (i === 3) {
                    // 步骤4: 视频 — 调用一键生成视频
                    await batchGenVideos();
                    // 执行后重新检查视频是否足够
                    const status4 = await api("/projects/" + projectId + "/pipeline-status");
                    if (!status4.steps[3]) {
                      throw new Error("视频生成不足，无法继续下一步");
                    }
                    markPipelineStep(4, "completed");
      } else if (i === 4) {
        // 步骤5: 合成 — 待实现
        markPipelineStep(5, "completed");
      } else if (i === 5) {
        // 步骤6: 发送 — 待实现
        markPipelineStep(6, "completed");
      }
    }

    alert("流水线执行完成！");
      } catch (e) {
        // 标记当前步骤为失败（显示红色边框）
        var errStep = startFrom;
        for (var si = startFrom; si < 6; si++) {
          if (!steps[si]) { errStep = si; break; }
        }
        markPipelineStep(errStep + 1, "error");
        alert("流水线执行失败: " + e.message);
      }
  finally { syncPipelineButtons(); }
}

let pipelinePollTimer = null;

function startPipelinePolling(runId) {
  if (pipelinePollTimer) clearInterval(pipelinePollTimer);
  pipelinePollTimer = setInterval(async () => {
    try {
      const run = await api("/pipeline/runs/" + runId);
      updatePipelineRunStatus(run);
      await loadPipelineRuns();
      if (run.status === "completed" || run.status === "error" || run.status === "cancelled") {
        clearInterval(pipelinePollTimer);
        pipelinePollTimer = null;
        syncPipelineButtons();
      }
    } catch {
      clearInterval(pipelinePollTimer);
      pipelinePollTimer = null;
    }
  }, 2000);
}

async function stopPipeline() {
  const stopBtn = document.getElementById("stopPipelineBtn");
  stopBtn.disabled = true;
  stopBtn.textContent = "⏹ 查找中...";
  
  // 实时查询最新运行记录，找到正在执行的流水线
  let runId = null;
  try {
    const runs = await api("/pipeline/runs");
    const running = runs.find((r) => r.status === "running");
    if (running) runId = running.run_id;
  } catch {}
  
  if (!runId) {
    runId = state.lastRunId; // 兜底
  }
  if (!runId) { alert("没有正在执行的流水线"); stopBtn.disabled = false; stopBtn.textContent = "⏹ 停止"; return; }
  
  stopBtn.textContent = "⏹ 停止中...";
  try {
    await api("/pipeline/runs/" + runId + "/cancel", { method: "POST" });
  } catch (e) { alert("停止失败: " + e.message); }
  finally {
    stopBtn.disabled = false;
    stopBtn.textContent = "⏹ 停止中";
  }
}

function updatePipelineRunStatus(run) {
  const container = document.getElementById("pipelineFlow");
  if (!container) return;
  const steps = run.steps || [];
  steps.forEach((step) => {
    const el = container.querySelector(`[data-step="${step.name}"]`);
    if (!el) return;
    el.className = `pipe-step pipe-${step.status}`;
    const nameEl = el.querySelector(".pipe-step-name");
    if (nameEl) { const icons = { pending: "⏳", running: "🔄", completed: "✅", error: "❌", skipped: "⏭️" }; nameEl.innerHTML = `${icons[step.status] || "⏳"} ${step.label}`; }
    const descEl = el.querySelector(".pipe-step-desc");
    if (descEl) {
      if (step.status === "completed" && step.output_summary) descEl.textContent = step.output_summary;
      else if (step.status === "error") descEl.textContent = "❌ " + (step.error || "失败");
      else if (step.status === "skipped") descEl.textContent = "已跳过（可选）";
      else descEl.textContent = step.description;
    }
  });
  const titleEl = container.querySelector(".pipeline-title");
  if (titleEl) { const icons = { idle: "📋", running: "🔄", completed: "✅ 完成", error: "❌ 失败" }; titleEl.textContent = `${icons[run.status] || "📋"} 完整流水线`; }
}

function syncPipelineButtons() {
  // 检查是否有正在执行的流水线，同步按钮状态
  const hasRunning = state.pipelineRuns.some((r) => r.status === "running");
  const btn = document.getElementById("runPipelineBtn");
  const stopBtn = document.getElementById("stopPipelineBtn");
  if (!btn || !stopBtn) return;
  if (hasRunning) {
    btn.style.display = "none";
    stopBtn.style.display = "inline-block";
    stopBtn.disabled = false;
    stopBtn.textContent = "⏹ 停止";
  } else {
    btn.style.display = "inline-block";
    btn.disabled = false;
    btn.textContent = "▶ 执行流水线";
    stopBtn.style.display = "none";
  }
}

async function loadPipelineRuns() {
  try {
    const projectId = state.currentProject ? state.currentProject.project_id : "";
    const runs = await api("/pipeline/runs" + (projectId ? "?project_id=" + projectId : ""));
    state.pipelineRuns = runs;
    
    // 同步按钮状态
    syncPipelineButtons();
    
    const listEl = document.getElementById("pipelineRunList");
    if (!listEl) return;
    if (runs.length === 0) { listEl.innerHTML = '<div class="pipeline-placeholder">暂无执行记录</div>'; return; }
    listEl.innerHTML = runs.map((r) => `
      <div class="run-card ${r.status}" onclick="showPipelineRunDetail('${r.run_id}')">
        <div class="run-card-header"><span class="run-status run-${r.status}">${statusIcon(r.status)} ${r.status}</span><span class="run-id">${r.run_id.slice(0, 12)}…</span><span class="run-time">${formatTime(r.created_at)}</span></div>
        <div class="run-card-steps">${(r.steps || []).map((s) => `<span class="step-dot step-${s.status}" title="${s.label}: ${s.status}"></span>`).join("")}</div>
      </div>`).join("");
  } catch (e) { console.warn("流水线记录加载失败:", e.message); }
}

async function showPipelineRunDetail(runId) {
  try { const run = await api("/pipeline/runs/" + runId); updatePipelineRunStatus(run); switchTab("pipeline"); }
  catch (e) { alert("加载详情失败: " + e.message); }
}

function statusIcon(status) { return { idle: "⏸", running: "🔄", completed: "✅", error: "❌" }[status] || "⏳"; }
function formatTime(iso) { if (!iso) return ""; const d = new Date(iso); return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }); }

// ========== 字数统计 ==========
function updateCharCount() {
  const el = document.getElementById("charCount");
  if (!el) return;
  const text = document.getElementById("storyInput").value;
  const count = text.replace(/\s/g, "").length;
  el.textContent = count + " 字";
}

// ========== AI 生成文案 ==========
async function generateScript() {
  if (!requireProject()) return;
  const topic = document.getElementById("scriptTopic").value.trim();
  if (!topic) { alert("请先输入文案主题"); return; }
  const btn = document.getElementById("genScriptBtn");
  const tone = document.getElementById("scriptTone").value;
  const wordCountRaw = document.getElementById("scriptWordCount").value.trim();
  const wordCount = wordCountRaw ? parseInt(wordCountRaw) || 0 : 0;
  // 视觉风格锚点
  var styleAnchor = "";
  if (selectedVisualStyle) {
    styleAnchor = selectedVisualStyle.video_anchor || "";
  }
  btn.disabled = true; btn.textContent = "⏳ 生成中...";

  try {
    // 创建异步任务
    const task = await api("/script/task", { body: {
      type: "generate",
      params: { topic, tone, style: styleAnchor, duration_seconds: 30, word_count: wordCount }
    }});
    const taskId = task.task_id;
    const taskKey = "zctools_task_generate_" + (state.currentProject ? state.currentProject.project_id : "_default");
    localStorage.setItem(taskKey, taskId);

    // 轮询结果
        const result = await _pollTask(taskId, taskKey);
        if (result && result.generated && result.script) {
          _handleGenerateResult(result);
        } else {
          alert("生成失败: " + (result?.error || "未知错误"));
        }
      } catch (e) { alert("生成失败: " + e.message); }
      finally { btn.disabled = false; btn.textContent = "✨ AI 生成"; }
    }

    function _handleGenerateResult(result) {
      document.getElementById("storyInput").value = result.script;
      localStorage.setItem(_projectKey("zctools_script"), result.script);
      updateCharCount();
      if (state.currentProject) saveProjectContent();
      markPipelineStep(2, "completed");
    }

// ========== AI 修改文案 ==========
async function modifyScript() {
  const instruction = document.getElementById("modifyInstruction").value.trim();
  const currentScript = document.getElementById("storyInput").value.trim();
  if (!currentScript) { alert("请先生成文案"); return; }
  if (!instruction) { alert("请输入修改要求"); return; }
  const btn = document.getElementById("modifyBtn");
  btn.disabled = true; btn.textContent = "⏳ 修改中...";
  try {
    // 创建异步任务
    const task = await api("/script/task", { body: {
      type: "modify",
      params: { topic: currentScript, custom_prompt: instruction }
    }});
    const taskId = task.task_id;
    const taskKey = "zctools_task_modify_" + (state.currentProject ? state.currentProject.project_id : "_default");
    localStorage.setItem(taskKey, taskId);

    // 轮询结果
        const result = await _pollTask(taskId, taskKey);
        if (result && result.modified && result.script) {
          _handleModifyResult(result);
        } else {
          alert("修改失败: " + (result?.error || "未知错误"));
        }
      } catch (e) { alert("修改失败: " + e.message); }
      finally { btn.disabled = false; btn.textContent = "✨ AI 修改"; }
    }

    function _handleModifyResult(result) {
      document.getElementById("storyInput").value = result.script;
      localStorage.setItem(_projectKey("zctools_script"), result.script);
      updateCharCount();
      if (state.currentProject) saveProjectContent();
    }

// ========== 系统提示词 ==========
async function loadPrompts() {
  try {
    state.prompts = await api("/prompts");
    // promptSelector 已替换为 visualStyleSelector，不再需要填充下拉
  } catch (e) { console.warn("提示词加载失败:", e.message); }
}

function onPromptChange() {
  // 已废弃 — 视觉风格预设使用 visualStyleSelector
}

function showPromptModal() {
  document.getElementById("promptModal").classList.add("show");
  renderPromptList();
  document.getElementById("newPromptName").value = "";
  document.getElementById("newPromptContent").value = "";
}

function renderPromptList() {
  const list = document.getElementById("promptList");
  if (!list) return;
  list.innerHTML = state.prompts.map((p) => `
    <div class="prompt-list-item">
      <div class="prompt-list-info">
        <strong>${p.builtin ? "★" : "✎"} ${p.name}</strong>
        <span class="prompt-list-preview">${p.content.slice(0, 80)}${p.content.length > 80 ? "..." : ""}</span>
      </div>
      <button class="btn btn-sm btn-outline" onclick="editPrompt('${p.id}')" title="编辑">✎</button>
      <button class="btn btn-sm btn-outline" onclick="deleteCustomPrompt('${p.id}')" style="color:var(--red)" title="删除">🗑</button>
    </div>`).join("");
}

function editPrompt(id) {
  const p = state.prompts.find(x => x.id === id);
  if (!p) return;
  document.getElementById("editPromptId").value = id;
  document.getElementById("newPromptName").value = p.name;
  document.getElementById("newPromptContent").value = p.content;
}

function clearPromptEditor() {
  document.getElementById("editPromptId").value = "";
  document.getElementById("newPromptName").value = "";
  document.getElementById("newPromptContent").value = "";
}

async function saveCustomPrompt() {
  const name = document.getElementById("newPromptName").value.trim();
  const content = document.getElementById("newPromptContent").value.trim();
  const editId = document.getElementById("editPromptId").value;
  if (!name || !content) { alert("请填写名称和内容"); return; }
  try {
    if (editId) {
      await api("/prompts/" + editId, { method: "PUT", body: { name, content } });
    } else {
      await api("/prompts", { body: { name, content } });
    }
    await loadPrompts();
    renderPromptList();
    clearPromptEditor();
    alert("已保存");
  } catch (e) { alert("保存失败: " + e.message); }
}

async function deleteCustomPrompt(id) {
  if (!confirm("删除此提示词？")) return;
  try {
    await api("/prompts/" + id, { method: "DELETE" });
    await loadPrompts();
    renderPromptList();
  } catch (e) { alert("删除失败: " + e.message); }
}

// ========== LLM 设置 ==========
function selectModel(model) {
  document.getElementById("llmModel").value = model;
  document.getElementById("modelListDropdown").style.display = "none";
}

async function loadLLMConfig() {
  try {
    const config = await api("/llm/config");
    document.getElementById("llmBaseUrl").value = config.base_url || "";
    document.getElementById("llmModel").value = config.model || "";
    document.getElementById("llmKeyStatus").textContent = config.has_key ? "🔑 已配置" : "❌ 未配置";
    document.getElementById("llmConfigInfo").innerHTML = config.has_key ? `状态：已配置 ✅ | 共 ${config.key_count} 个 Key` : "状态：未配置 ❌ 请先填写 API 地址和 Key，然后测试连接";
      } catch (e) { document.getElementById("llmConfigInfo").textContent = "加载失败: " + e.message; }
      // 同时加载 key 列表
      setTimeout(loadLLMKeys, 100);
}

async function loadLLMKeys() {
  try {
    const data = await api("/llm/keys");
    const list = document.getElementById("llmKeyList");
    if (!list) return;
    if (!data.keys || data.keys.length === 0) {
      list.innerHTML = '<div class="settings-info" style="margin-top:4px">暂无 API Key，请添加</div>';
      return;
    }
    list.innerHTML = data.keys.map(k => `
                  <div class="key-item ${k.is_active ? 'key-active' : ''}" onclick="selectLLMKey('${k.id}')" style="cursor:pointer">
                                      <div class="key-col-left">
                                        <span class="key-dot ${k.is_active ? 'dot-active' : (k.failed_at ? 'dot-dead' : 'dot-ok')}"></span>
                                        <span class="key-label" onclick="event.stopPropagation();renameLLMKey('${k.id}','${k.label}')" title="点击重命名">${k.label}</span>
                                      </div>
                                      <div class="key-col-id">
                                        <span class="key-id">#${k.id}</span>
                                      </div>
                                      <div class="key-col-model">
                                        ${k.model ? `<span class="key-model">${k.model}</span>` : ''}
                                      </div>
                                      <div class="key-col-right">
                                                            ${k.is_active ? '<span class="key-badge key-badge-active">当前</span>' : ''}
                                                            ${k.failed_at ? '<span class="key-badge key-badge-dead">已挂</span>' : '<span class="key-badge key-badge-ok">正常</span>'}
                                                            <span class="key-delete-btn" onclick="event.stopPropagation();deleteLLMKey('${k.id}')" title="删除">✕</span>
                                                          </div>
                                    </div>
                `).join("");
  } catch (e) { console.warn("加载 Key 列表失败:", e.message); }
}

async function addLLMKey() {
  const input = document.getElementById("newKeyInput");
  const key = input.value.trim();
  if (!key) { alert("请输入 API Key"); return; }
  try {
    await api("/llm/keys", { body: { api_key: key } });
    input.value = "";
    loadLLMKeys();
  } catch (e) { alert("添加失败: " + e.message); }
}

async function selectLLMKey(id) {
  // 把选中的 key 设为当前活跃 key
  try {
    await api("/llm/keys/" + id + "/activate", { method: "POST" });
    loadLLMKeys();
  } catch (e) { alert("切换失败: " + e.message); }
}

async function renameLLMKey(id, currentLabel) {
  const newLabel = prompt("重命名 Key：", currentLabel);
  if (!newLabel || newLabel === currentLabel) return;
  try {
    await api("/llm/keys/" + id + "/rename", { method: "POST", body: { label: newLabel } });
    loadLLMKeys();
  } catch (e) { alert("重命名失败: " + e.message); }
}

async function deleteLLMKey(id) {
  if (!confirm("确定删除这个 Key？")) return;
  try {
    await api("/llm/keys/" + id, { method: "DELETE" });
    loadLLMKeys();
  } catch (e) { alert("删除失败: " + e.message); }
}

async function fetchModels() {
  const input = document.getElementById("llmModel");
  const dl = document.getElementById("modelList");
  const btn = document.getElementById("fetchModelsBtn");
  const baseUrl = document.getElementById("llmBaseUrl").value.trim();
  const apiKey = document.getElementById("llmApiKey").value.trim();
  if (!baseUrl || !apiKey) { alert("请先填写 API 地址和 Key 并测试连接"); return; }
  btn.disabled = true; btn.textContent = "⏳";
  input.value = "";  // 清空输入框，让 datalist 显示全部选项
  try {
    const url = "/llm/models?base_url=" + encodeURIComponent(baseUrl) + "&api_key=" + encodeURIComponent(apiKey);
    const result = await api(url);
    dl.innerHTML = "";
    if (result.models && result.models.length > 0) {
      result.models.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m;
        dl.appendChild(opt);
      });
    }
    btn.textContent = "🔄 刷新";
  } catch (e) {
    btn.textContent = "🔄 刷新";
  }
  btn.disabled = false;
}

async function saveLLMConfig() {
  const baseUrl = document.getElementById("llmBaseUrl").value.trim();
  const model = document.getElementById("llmModel").value.trim();
  const keyInput = document.getElementById("newKeyInput").value.trim();
  if (!baseUrl) { alert("请先填写 API 地址"); return; }
  if (!model) { alert("请先选择模型"); return; }
  if (!keyInput) { alert("请先输入 API Key"); return; }
    try {
        // 先添加 key（带上当前选中的模型）
        const curModel = document.getElementById("llmModel").value.trim();
        await api("/llm/keys", { body: { api_key: keyInput, model: curModel } });
        document.getElementById("newKeyInput").value = "";
        // 再保存配置
        const result = await api("/llm/config", { body: { base_url: baseUrl, model: model } });
    document.getElementById("llmConfigInfo").innerHTML = result.configured ? `状态：已配置 ✅ | 共 ${result.key_count} 个 Key` : "状态：未配置 ❌";
    loadLLMKeys();
    if (result.configured) alert("✅ 已添加 Key 并保存配置！");
  } catch (e) { alert("操作失败: " + e.message); }
}

async function testLLMConfig() {
  const baseUrl = document.getElementById("llmBaseUrl").value.trim();
  const apiKey = document.getElementById("newKeyInput").value.trim();
  if (!baseUrl) { alert("请先填写 API 地址"); return; }
  if (!apiKey) { alert("请先输入 API Key"); return; }
  const btn = document.querySelector(".settings-actions .btn-outline");
  const resultEl = document.getElementById("llmTestResult");
  btn.disabled = true; btn.textContent = "⏳ 测试中..."; resultEl.textContent = "";
  try {
        const result = await api("/llm/test", { method: "POST", body: { base_url: baseUrl, api_key: apiKey } });
        resultEl.innerHTML = result.ok ? `✅ 连接成功: "${result.reply}"` : "❌ 连接失败，请检查配置";
        resultEl.className = result.ok ? "settings-test-result success" : "settings-test-result error";
        if (result.ok) {
          // 测试成功后拉取模型列表并显示为下拉选择
          const modelsResult = await api("/llm/models?base_url=" + encodeURIComponent(baseUrl) + "&api_key=" + encodeURIComponent(document.getElementById("newKeyInput").value.trim()));
          const dropdown = document.getElementById("modelListDropdown");
          const modelInput = document.getElementById("llmModel");
          if (modelsResult.models && modelsResult.models.length > 0) {
            dropdown.innerHTML = modelsResult.models.map(m => `<div class="model-dropdown-item" onclick="selectModel('${m}')">${m}</div>`).join("");
            dropdown.style.display = "block";
          }
        }
    } catch (e) { resultEl.textContent = "❌ 测试失败: " + e.message; resultEl.className = "settings-test-result error"; }
    finally { btn.disabled = false; btn.textContent = "📡 测试连接"; }
  }

  // ========== 角色管理 ==========
          async function loadCharacters() {
                      const list = document.getElementById("charList");
                      if (!list) return;
                      // 同步设置页项目选择器
                      _syncSettingsSelector();
                      if (!state.currentProject) {
              list.innerHTML = '<div class="settings-hint" style="padding:8px 0">请先选择项目</div>';
              return;
            }
        try {
          const chars = await api("/characters?project_id=" + state.currentProject.project_id);
        if (!chars || chars.length === 0) {
          list.innerHTML = '<div class="settings-hint" style="padding:8px 0">暂无角色，点击添加</div>';
          return;
        }
      list.innerHTML = chars.map((c, ci) => `
                                <div class="char-item" data-char-idx="${ci}">
                                  <div class="char-cols">
                                    <!-- 列一：上传图片 + 生成三视图 -->
                                    <div class="char-col">
                                      <div class="char-upload-gen-layout">
                                        <div class="char-upload-area" onclick="uploadCharImage('${c.id}')">
                                          ${c.uploaded_image
                                            ? `<img src="${c.uploaded_image}" class="char-upload-img">`
                                            : '<div class="char-upload-placeholder">+<br>点击上传图片</div>'}
                                          ${c.uploaded_image ? `<span class="char-clear-btn" onclick="event.stopPropagation();clearUploadedImage('${c.id}')">清空</span>` : ""}
                                        </div>
                                        <input type="file" id="charUpload_${c.id}" accept="image/*" style="display:none" onchange="handleCharUpload(event,'${c.id}')">
                                        <div class="char-gen-btn-area">
                                          <button class="char-gen-btn" onclick="genThreeView('${c.id}')" id="gen3Btn_${c.id}">🖼 生成三视图</button>
                                        </div>
                                        <div class="char-preview-area" id="charPreview_${c.id}">
                                          ${c.three_view && c.three_view.images && c.three_view.images.length > 0
                                                      ? `<img src="${c.three_view.images[0]}" class="char-preview-img">`
                                            : '<div class="char-preview-placeholder">生成后预览</div>'}
                                        </div>
                                      </div>
                                    </div>
                              <!-- 列二：角色提示词 -->
                              <div class="char-col char-col-prompt">
                                <div class="char-col-title"><span class="char-name-display" id="charNameDisplay_${c.id}" onclick="renameCharacter('${c.id}')">${escHtml(c.name)}</span> <button class="char-del-btn" onclick="deleteCharacter('${c.id}')" title="删除角色">弃</button></div>
                                <textarea class="char-prompt-textarea" placeholder="角色名称、风格、个性、背景等详细描述，用于生成时保持角色一致性..." onchange="updateCharField('${c.id}','description',this.value)">${escHtml(c.description || "")}</textarea>
                              </div>
                            </div>
                          </div>
                        `).join("");
    } catch {}
  }

  async function addCharacter() {
    if (!state.currentProject) { alert("请先选择项目"); return; }
    try {
      await api("/characters", {
        method: "POST",
        body: {
          project_id: state.currentProject.project_id,
          name: "新角色",
          style: "",
          voice: { gender: "", tone: "", speed: "中" },
          description: "",
        }
      });
      await loadCharacters();
    } catch (e) { alert("添加失败: " + e.message); }
  }

  async function deleteCharacter(charId) {
    if (!state.currentProject || !confirm("删除该角色？")) return;
    try {
      await api("/characters/" + charId + "?project_id=" + state.currentProject.project_id, { method: "DELETE" });
      await loadCharacters();
    } catch (e) { alert("删除失败: " + e.message); }
  }

  async function updateCharField(charId, field, value) {
    if (!state.currentProject) return;
    const chars = await api("/characters?project_id=" + state.currentProject.project_id);
    const c = chars.find(x => x.id === charId);
    if (!c) return;
    const updates = {
      project_id: state.currentProject.project_id,
      name: c.name,
      style: c.style || "",
      voice: c.voice || { gender: "", tone: "", speed: "中" },
      description: "",
    };
    if (field === "name") updates.name = value;
    else if (field === "style") updates.style = value;
    else if (field === "personality") {
      if (!updates.voice) updates.voice = { gender: "", tone: "", speed: "中" };
      updates.voice.tone = value;
    }
    await api("/characters/" + charId, { method: "PUT", body: updates });
      }

      // 重命名角色
      async function renameCharacter(charId) {
        const name = prompt("输入新名称：");
        if (!name) return;
        await updateCharField(charId, "name", name);
        const el = document.getElementById("charNameDisplay_" + charId);
        if (el) el.textContent = name;
      }

      // 上传角色图片
  function uploadCharImage(charId) {
    document.getElementById("charUpload_" + charId).click();
  }
  async function handleCharUpload(event, charId) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async function(e) {
      const dataUrl = e.target.result;
      // 保存到角色数据
            const chars = await api("/characters?project_id=" + state.currentProject.project_id);
            const c = chars.find(x => x.id === charId);
            if (!c) return;
            await api("/characters/" + charId, {
              method: "PUT",
              body: {
                project_id: state.currentProject.project_id,
                name: c.name,
                style: c.style || "",
                voice: c.voice || { gender: "", tone: "", speed: "中" },
                description: "",
                uploaded_image: dataUrl,
              }
            });
      await loadCharacters();
    };
    reader.readAsDataURL(file);
      }

      // 清空上传的图片
      async function clearUploadedImage(charId) {
        if (!state.currentProject) return;
        const chars = await api("/characters?project_id=" + state.currentProject.project_id);
        const c = chars.find(x => x.id === charId);
        if (!c) return;
        await api("/characters/" + charId, {
          method: "PUT",
          body: {
            project_id: state.currentProject.project_id,
            name: c.name,
            style: c.style || "",
            voice: c.voice || { gender: "", tone: "", speed: "中" },
            description: "",
            uploaded_image: "",
          }
        });
        await loadCharacters();
      }

      // ========== 角色三视图生成 ==========
  const THREE_VIEW_PROMPT = `生成该角色的三视图拼图，布局要求：
  - 左下角：正面全身图（主视图）
  - 左上角：背面全身图
  - 右下角：侧面全身图（侧视图）
  - 右上角：原图（正面细节图，展示角色面部和服装细节）
  要求：全身图，四张图角色形象完全一致，服装、发色、体型统一。`;

const PROP_THREE_VIEW_PROMPT = `生成该道具的三视图拼图，布局要求：
  - 左下角：正面主视图（道具的正面展示）
  - 左上角：背面视图（道具的背面展示）
  - 右下角：侧面视图（道具的侧面展示）
  - 右上角：原图（道具的细节特写）
  要求：四张图道具外观完全一致，材质、颜色、结构统一，纯色背景。`;

  async function genThreeView(charId) {
    if (!state.currentProject) { alert("请先选择项目"); return; }
    const chars = await api("/characters?project_id=" + state.currentProject.project_id);
    const char = chars.find(c => c.id === charId);
    if (!char) { alert("角色不存在"); return; }

    const desc = [char.style, char.voice && char.voice.tone].filter(Boolean).join("，");
        const prompt = THREE_VIEW_PROMPT + "\n角色描述：" + (desc || char.name);
        // 如果有上传图片，作为参考图
                const refs = char.uploaded_image ? [char.uploaded_image] : [];
        const btn = document.getElementById("gen3Btn_" + charId);
    if (!btn) return;
    btn.disabled = true; btn.textContent = "⏳";

    try {
      const res = await api("/generate-frame", {
              body: { prompt: prompt, aspect_ratio: "16:9", mode: "three_view", project_id: state.currentProject.project_id, shot_idx: 0, reference_images: refs }
      });
      if (res.success && res.image_url) {
        const threeViewData = { images: [res.image_url], prompt: prompt };
        await api("/characters/" + charId, {
          method: "PUT",
          body: {
            project_id: state.currentProject.project_id,
            name: char.name,
            style: char.style || "",
            voice: char.voice || { gender: "", tone: "", speed: "中" },
            description: "",
            three_view: threeViewData,
          }
        });
        await loadCharacters();
        alert("三视图生成成功！");
      } else {
        alert("生成失败: " + (res.error || "未知错误"));
      }
    } catch (e) { alert("生成失败: " + e.message); }
    finally { btn.disabled = false; btn.textContent = "🖼 生成三视图"; }
  }

  // 转义 HTML 特殊字符
    function escHtml(str) {
          return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
        }

        // 同步设置页项目选择器
        function _syncSettingsSelector() {
          const pss = document.getElementById("psSettings");
          if (!pss) return;
          try {
            const projs = state.projects;
            if (!projs || projs.length === 0) return;
            pss.innerHTML = '<option value="">— 选择项目 —</option>' + projs.map(p => `<option value="${p.project_id}">${p.project_name}</option>`).join("");
            if (state.currentProject) pss.value = state.currentProject.project_id;
          } catch {}
        }

        // ========== 场景管理 ==========
async function loadScenes() {
          const list = document.getElementById("sceneList");
          if (!list) return;
          _syncSettingsSelector();
          if (!state.currentProject) {
        list.innerHTML = '<div class="settings-hint" style="padding:8px 0">请先选择项目</div>';
        return;
      }
      try {
        const scenes = await api("/scenes?project_id=" + state.currentProject.project_id);
        if (!scenes || scenes.length === 0) {
          list.innerHTML = '<div class="settings-hint" style="padding:8px 0">暂无场景，点击添加</div>';
          return;
        }
        list.innerHTML = scenes.map((s, si) => `
          <div class="char-item" data-scene-idx="${si}">
            <div class="char-cols">
              <!-- 列一：上传图片 + 修改原图 -->
              <div class="char-col">
                <div class="char-upload-gen-layout">
                  <div class="char-upload-area" onclick="uploadSceneImage('${s.id}')">
                    ${s.uploaded_image
                      ? `<img src="${s.uploaded_image}" class="char-upload-img">`
                      : '<div class="char-upload-placeholder">+<br>点击上传图片</div>'}
                    ${s.uploaded_image ? `<span class="char-clear-btn" onclick="event.stopPropagation();clearSceneImage('${s.id}')">清空</span>` : ""}
                  </div>
                  <input type="file" id="sceneUpload_${s.id}" accept="image/*" style="display:none" onchange="handleSceneUpload(event,'${s.id}')">
                  <div class="char-gen-btn-area">
                    <button class="char-gen-btn" onclick="genSceneImage('${s.id}')" id="genSceneBtn_${s.id}">🖼 修改原图</button>
                  </div>
                  <div class="char-preview-area" id="scenePreview_${s.id}">
                    ${s.generated_image
                      ? `<img src="${s.generated_image}" class="char-preview-img">`
                      : '<div class="char-preview-placeholder">修改后预览</div>'}
                  </div>
                </div>
              </div>
              <!-- 列二：场景提示词 -->
              <div class="char-col char-col-prompt">
                <div class="char-col-title"><span class="char-name-display" id="sceneNameDisplay_${s.id}" onclick="renameScene('${s.id}')">${escHtml(s.name === "新场景" ? "未命名" : s.name)}</span> <button class="char-del-btn" onclick="deleteScene('${s.id}')" title="删除场景">弃</button></div>
                <input class="char-field" value="${escHtml(s.style || "")}" placeholder="场景风格（如：古风庭院）" onchange="updateSceneField('${s.id}','style',this.value)" style="margin-bottom:4px;width:100%;box-sizing:border-box">
                <textarea class="char-prompt-textarea" placeholder="该场景的详细描述，用于生成时保持场景一致性..." onchange="updateSceneField('${s.id}','description',this.value)">${escHtml(s.description || "")}</textarea>
              </div>
            </div>
          </div>
        `).join("");
      } catch {}
    }

    async function addScene() {
      if (!state.currentProject) { alert("请先选择项目"); return; }
      try {
        await api("/scenes", {
          method: "POST",
          body: { project_id: state.currentProject.project_id, name: "新场景", style: "", description: "" }
        });
        await loadScenes();
      } catch (e) { alert("添加失败: " + e.message); }
    }

    async function deleteScene(sceneId) {
      if (!state.currentProject || !confirm("删除该场景？")) return;
      try {
        await api("/scenes/" + sceneId + "?project_id=" + state.currentProject.project_id, { method: "DELETE" });
        await loadScenes();
      } catch (e) { alert("删除失败: " + e.message); }
    }

    async function updateSceneField(sceneId, field, value) {
      if (!state.currentProject) return;
      const scenes = await api("/scenes?project_id=" + state.currentProject.project_id);
      const s = scenes.find(x => x.id === sceneId);
      if (!s) return;
      const updates = { project_id: state.currentProject.project_id, name: s.name, style: s.style || "", description: s.description || "" };
      if (field === "name") updates.name = value;
      else if (field === "style") updates.style = value;
      else if (field === "description") updates.description = value;
      await api("/scenes/" + sceneId, { method: "PUT", body: updates });
    }

    async function renameScene(sceneId) {
      const name = prompt("输入新名称：");
      if (!name) return;
      await updateSceneField(sceneId, "name", name);
      const el = document.getElementById("sceneNameDisplay_" + sceneId);
      if (el) el.textContent = name;
    }

    function uploadSceneImage(sceneId) {
      document.getElementById("sceneUpload_" + sceneId).click();
    }
    async function handleSceneUpload(event, sceneId) {
      const file = event.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async function(e) {
        const dataUrl = e.target.result;
        const scenes = await api("/scenes?project_id=" + state.currentProject.project_id);
        const s = scenes.find(x => x.id === sceneId);
        if (!s) return;
        await api("/scenes/" + sceneId, {
          method: "PUT",
          body: { project_id: state.currentProject.project_id, name: s.name, style: s.style || "", description: s.description || "", uploaded_image: dataUrl }
        });
        await loadScenes();
      };
      reader.readAsDataURL(file);
    }

    async function clearSceneImage(sceneId) {
      if (!state.currentProject) return;
      const scenes = await api("/scenes?project_id=" + state.currentProject.project_id);
      const s = scenes.find(x => x.id === sceneId);
      if (!s) return;
      await api("/scenes/" + sceneId, {
        method: "PUT",
        body: { project_id: state.currentProject.project_id, name: s.name, style: s.style || "", description: s.description || "", uploaded_image: "" }
      });
      await loadScenes();
    }

    async function genSceneImage(sceneId) {
      if (!state.currentProject) { alert("请先选择项目"); return; }
      const scenes = await api("/scenes?project_id=" + state.currentProject.project_id);
      const s = scenes.find(x => x.id === sceneId);
      if (!s) { alert("场景不存在"); return; }
      const prompt = "修改场景图，保持原图构图和主体不变，仅根据描述调整细节。" + (s.style || s.name) + "，" + (s.description || "");
      const btn = document.getElementById("genSceneBtn_" + sceneId);
      if (!btn) return;
      btn.disabled = true; btn.textContent = "⏳";
      try {
        const refs = s.uploaded_image ? [s.uploaded_image] : [];
        const res = await api("/generate-frame", {
          body: { prompt: prompt, aspect_ratio: "16:9", mode: "scene", project_id: state.currentProject.project_id, shot_idx: 0, reference_images: refs }
        });
        if (res.success && res.image_url) {
          await api("/scenes/" + sceneId, {
            method: "PUT",
            body: { project_id: state.currentProject.project_id, name: s.name, style: s.style || "", description: s.description || "", generated_image: res.image_url }
          });
          await loadScenes();
          alert("场景图修改成功！");
        } else {
          alert("修改失败: " + (res.error || "未知错误"));
        }
      } catch (e) { alert("修改失败: " + e.message); }
      finally { btn.disabled = false; btn.textContent = "🖼 修改原图"; }
    }          // ========== 道具管理 ==========
async function loadProps() {
            const list = document.getElementById("propList");
            if (!list) return;
            _syncSettingsSelector();
            if (!state.currentProject) {
              list.innerHTML = '<div class="settings-hint" style="padding:8px 0">请先选择项目</div>';
              return;
            }
            try {
              const props = await api("/props?project_id=" + state.currentProject.project_id);
              if (!props || props.length === 0) {
                list.innerHTML = '<div class="settings-hint" style="padding:8px 0">暂无道具，点击添加</div>';
                return;
              }
              list.innerHTML = props.map((p, pi) => `
                <div class="char-item" data-prop-idx="${pi}">
                  <div class="char-cols">
                    <!-- 列一：上传图片 + 生成三视图 -->
                    <div class="char-col">
                      <div class="char-upload-gen-layout">
                        <div class="char-upload-area" onclick="uploadPropImage('${p.id}')">
                          ${p.uploaded_image
                            ? `<img src="${p.uploaded_image}" class="char-upload-img">`
                            : '<div class="char-upload-placeholder">+<br>点击上传图片</div>'}
                          ${p.uploaded_image ? `<span class="char-clear-btn" onclick="event.stopPropagation();clearPropImage('${p.id}')">清空</span>` : ""}
                        </div>
                        <input type="file" id="propUpload_${p.id}" accept="image/*" style="display:none" onchange="handlePropUpload(event,'${p.id}')">
                        <div class="char-gen-btn-area">
                          <button class="char-gen-btn" onclick="genPropThreeView('${p.id}')" id="genProp3Btn_${p.id}">🖼 生成三视图</button>
                        </div>
                        <div class="char-preview-area" id="propPreview_${p.id}">
                          ${p.three_view && p.three_view.images && p.three_view.images.length > 0
                            ? `<img src="${p.three_view.images[0]}" class="char-preview-img">`
                            : '<div class="char-preview-placeholder">生成后预览</div>'}
                        </div>
                      </div>
                    </div>
                    <!-- 列二：道具提示词 -->
                    <div class="char-col char-col-prompt">
                      <div class="char-col-title"><span class="char-name-display" id="propNameDisplay_${p.id}" onclick="renameProp('${p.id}')">${escHtml(p.name)}</span> <button class="char-del-btn" onclick="deleteProp('${p.id}')" title="删除道具">弃</button></div>
                      <textarea class="char-prompt-textarea" placeholder="道具名称、风格、外观、材质等详细描述，用于生成时保持道具一致性..." onchange="updatePropField('${p.id}','description',this.value)">${escHtml(p.description || "")}</textarea>
                    </div>
                  </div>
                </div>
              `).join("");
            } catch {}
          }
          async function addProp() {
            if (!state.currentProject) { alert("请先选择项目"); return; }
            try {
              await api("/props", {
                method: "POST",
                body: { project_id: state.currentProject.project_id, name: "新道具", style: "", voice: { gender: "", tone: "", speed: "中" }, description: "" }
              });
              await loadProps();
            } catch (e) { alert("添加失败: " + e.message); }
          }
          async function deleteProp(propId) {
            if (!state.currentProject || !confirm("删除该道具？")) return;
            try {
              await api("/props/" + propId + "?project_id=" + state.currentProject.project_id, { method: "DELETE" });
              await loadProps();
            } catch (e) { alert("删除失败: " + e.message); }
          }
          async function updatePropField(propId, field, value) {
            if (!state.currentProject) return;
            const props = await api("/props?project_id=" + state.currentProject.project_id);
            const p = props.find(x => x.id === propId);
            if (!p) return;
            const updates = { project_id: state.currentProject.project_id, name: p.name, style: p.style || "", voice: p.voice || { gender: "", tone: "", speed: "中" }, description: "" };
            if (field === "name") updates.name = value;
            else if (field === "style") updates.style = value;
            else if (field === "personality") { if (!updates.voice) updates.voice = { gender: "", tone: "", speed: "中" }; updates.voice.tone = value; }
            await api("/props/" + propId, { method: "PUT", body: updates });
          }
          async function renameProp(propId) {
            const name = prompt("输入新名称：");
            if (!name) return;
            await updatePropField(propId, "name", name);
            const el = document.getElementById("propNameDisplay_" + propId);
            if (el) el.textContent = name;
          }
          function uploadPropImage(propId) {
            document.getElementById("propUpload_" + propId).click();
          }
          async function handlePropUpload(event, propId) {
            const file = event.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = async function(e) {
              const dataUrl = e.target.result;
              const props = await api("/props?project_id=" + state.currentProject.project_id);
              const p = props.find(x => x.id === propId);
              if (!p) return;
              await api("/props/" + propId, {
                method: "PUT",
                body: { project_id: state.currentProject.project_id, name: p.name, style: p.style || "", voice: p.voice || { gender: "", tone: "", speed: "中" }, description: "", uploaded_image: dataUrl }
              });
              await loadProps();
            };
            reader.readAsDataURL(file);
          }
          async function clearPropImage(propId) {
            if (!state.currentProject) return;
            const props = await api("/props?project_id=" + state.currentProject.project_id);
            const p = props.find(x => x.id === propId);
            if (!p) return;
            await api("/props/" + propId, {
              method: "PUT",
              body: { project_id: state.currentProject.project_id, name: p.name, style: p.style || "", voice: p.voice || { gender: "", tone: "", speed: "中" }, description: "", uploaded_image: "" }
            });
            await loadProps();
          }
          async function genPropThreeView(propId) {
            if (!state.currentProject) { alert("请先选择项目"); return; }
            const props = await api("/props?project_id=" + state.currentProject.project_id);
            const p = props.find(x => x.id === propId);
            if (!p) { alert("道具不存在"); return; }
            const desc = [p.style, p.voice && p.voice.tone].filter(Boolean).join("，");
            const prompt = PROP_THREE_VIEW_PROMPT + "\n道具描述：" + (desc || p.name);
            const refs = p.uploaded_image ? [p.uploaded_image] : [];
            const btn = document.getElementById("genProp3Btn_" + propId);
            if (!btn) return;
            btn.disabled = true; btn.textContent = "⏳";
            try {
              const res = await api("/generate-frame", {
                body: { prompt: prompt, aspect_ratio: "16:9", mode: "character", project_id: state.currentProject.project_id, shot_idx: 0, reference_images: refs }
              });
              if (res.success && res.image_url) {
                await api("/props/" + propId, {
                  method: "PUT",
                  body: { project_id: state.currentProject.project_id, name: p.name, style: p.style || "", voice: p.voice || { gender: "", tone: "", speed: "中" }, description: "", three_view: { images: [res.image_url] } }
                });
                await loadProps();
                alert("三视图生成成功！");
              } else {
                alert("生成失败: " + (res.error || "未知错误"));
              }
            } catch (e) { alert("生成失败: " + e.message); }
            finally { btn.disabled = false; btn.textContent = "🖼 生成三视图"; }
          }
// ========== 弹窗关闭 ==========
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("modal-overlay")) e.target.classList.remove("show");
});