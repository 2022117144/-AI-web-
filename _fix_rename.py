import re

with open(r'D:/万象AI改/web_frontend/js/app.js', encoding='utf-8') as f:
    content = f.read()

# 找到错误段
# 当前: <span class="char-name-display" onclick="renameCharacter('${c.id}')" title="删除角色">弃</button>
# 应该: <span class="char-name-display" onclick="renameCharacter('${c.id}')">${escHtml(c.name)}</span> <button class="char-del-btn" onclick="deleteCharacter('${c.id}')" title="删除角色">弃</button>

old = '<span class="char-name-display" onclick="renameCharacter'
idx = content.find(old)
if idx == -1:
    print('ERROR: not found')
    exit(1)

# 找到从该span到</button>的完整片段
end_idx = content.find('</button>', idx)
error_segment = content[idx:end_idx + len('</button>')]
print('Error segment:', repr(error_segment[:200]))

# 构建正确内容
correct = '<span class="char-name-display" onclick="renameCharacter'
correct += "('${c.id}')\">${escHtml(c.name)}</span>"
correct += ' <button class="char-del-btn" onclick="deleteCharacter'
correct += "('${c.id}')\" title=\"删除角色\">弃</button>"

content = content.replace(error_segment, correct)

with open(r'D:/万象AI改/web_frontend/js/app.js', 'w', encoding='utf-8') as f:
    f.write(content)

# 验证
idx2 = content.find('char-name-display')
if idx2 > -1:
    print('Fixed!')
    print(content[idx2:idx2+200])
else:
    print('Still broken')