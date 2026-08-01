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
            const prompt = "生成一张道具三视图：" + (p.name) + "，" + (p.description || "");
            const btn = document.getElementById("genProp3Btn_" + propId);
            if (!btn) return;
            btn.disabled = true; btn.textContent = "⏳";
            try {
              const res = await api("/generate-frame", {
                body: { prompt: prompt, aspect_ratio: "16:9", mode: "character", project_id: state.currentProject.project_id, shot_idx: 0 }
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