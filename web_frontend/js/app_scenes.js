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
      const prompt = "修改场景图：" + (s.style || s.name) + "，" + (s.description || "");
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
    }