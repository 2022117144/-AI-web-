const fs=require('fs'),vm=require('vm'),assert=require('assert');
const root=require('path').resolve(__dirname, '../web_frontend') + '/';
for(const file of ['index.html','zc_index.html']){
  const html=fs.readFileSync(root+file,'utf8');
  let count=0;
  for(const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)){
    if(!/\bsrc\s*=/.test(match[1])) { new vm.Script(match[2],{filename:file+':inline'+count++}); }
  }
  console.log(file+': '+count+' inline scripts parse');
}
for(const file of ['js/app.js','js/media-client.js'])new vm.Script(fs.readFileSync(root+file,'utf8'),{filename:file});
const main=fs.readFileSync(root+'index.html','utf8'),app=fs.readFileSync(root+'js/app.js','utf8');
function extract(source,name,next){
  return source.slice(source.indexOf('function '+name+'('),source.indexOf('function '+next+'('));
}
let saved;
const context=vm.createContext({console,API_BASE:'',sbCurrentProject:'demo',
  sbShots:[{originalShot:{duration:7,video_prompt:'keep video prompt',framing:'close'},originalData:{custom:'keep'},
            script:'测试',prompt:'picture',firstFramePrompt:'start',lastFramePrompt:'end',
            video:'/api/project-files/demo/视频/shot_0.mp4'}],
  fetch:async (url,options)=>{saved=JSON.parse(options.body);return {ok:true,json:async()=>({})}}});
vm.runInContext(extract(main,'sbMediaUrl','sbLoadFromProject'),context);
vm.runInContext(extract(main,'saveSbData','loadSbData'),context);
vm.runInContext(extract(app,'srtTime','renderSRT'),context);
(async()=>{
  assert.equal(vm.runInContext("sbMediaUrl('', 'D:/万象AI改/zc_backend/data/project_content/demo/视频/shot_0.mp4')",context),'/api/project-files/demo/视频/shot_0.mp4');
  assert.equal(vm.runInContext("sbMediaUrl('', 'demo/视频/shot_0.mp4')",context),'/api/project-files/demo/视频/shot_0.mp4');
  assert.equal(vm.runInContext('srtTime(0)',context),'00:00:00,000');
  assert.equal(vm.runInContext('srtTime(65.123)',context),'00:01:05,123');
  await vm.runInContext('saveSbData()',context);
  assert.equal(saved.shots[0].duration,7);assert.equal(saved.shots[0].video_prompt,'keep video prompt');
  assert.equal(saved.shots[0].first_frame_prompt,'start');assert.equal(saved.shot_data[0].custom,'keep');
  console.log('Media URLs, subtitle timecodes and storyboard metadata regression: OK');
})().catch(e=>{console.error(e);process.exitCode=1;});
