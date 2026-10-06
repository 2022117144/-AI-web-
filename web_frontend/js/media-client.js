/* Project-scoped media tasks. A run ID is the only target for cancellation. */
(function () {
  'use strict';
  const watchers = new Map();
  async function request(path, options) {
    const response = await fetch('/api' + path, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || data.error || '媒体任务请求失败');
    return data;
  }
  async function start(projectId, config) {
    const run = await request('/pipeline/run', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({project_id: projectId, config: config || {}})});
    localStorage.setItem('wx_media_run_' + projectId, run.run_id);
    return run;
  }
  function watch(runId, onUpdate) {
    if (watchers.has(runId)) {
      const existing = watchers.get(runId);
      if (onUpdate) existing.listeners.add(onUpdate);
      return existing.promise;
    }
    const entry = {listeners: new Set(onUpdate ? [onUpdate] : [])};
    watchers.set(runId, entry);
    entry.promise = (async function () {
      let failures = 0;
      try {
        while (true) {
          let run;
          try { run = await request('/pipeline/runs/' + encodeURIComponent(runId)); failures = 0; }
          catch (error) {
            if (++failures >= 5) throw new Error('暂时无法读取任务状态，请重新进入流水线查看；后台任务可能仍在执行');
            await new Promise(resolve => setTimeout(resolve, 1500)); continue;
          }
          entry.listeners.forEach(listener => listener(run));
          if (['completed', 'error', 'cancelled'].includes(run.status)) return run;
          await new Promise(resolve => setTimeout(resolve, 1200));
        }
      } finally { watchers.delete(runId); }
    })();
    return entry.promise;
  }
  async function cancel(runId, projectId) {
    const run = await request('/pipeline/runs/' + encodeURIComponent(runId));
    if (run.project_id !== projectId) throw new Error('任务与当前项目不一致');
    return request('/pipeline/runs/' + encodeURIComponent(runId) + '/cancel', {method: 'POST'});
  }
  async function voice(projectId, shotIndex, onUpdate) {
    const run = await start(projectId, {action: 'voice', ...(shotIndex === undefined ? {} : {shot_index: shotIndex})});
    const final = await watch(run.run_id, onUpdate);
    if (final.status !== 'completed') throw new Error(final.error || '配音未完成');
    return request('/projects/' + encodeURIComponent(projectId) + '/content');
  }
  window.WXMedia = {request, start, watch, cancel, voice};
})();
