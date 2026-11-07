/* DID custom single-piece d100. Physical orientation determines every result.
   The existing DiceBox engine continues to own d4, d6, d8, d10, d12 and d20. */
import { THREE, CANNON } from './dice_libs/d100_deps.js';

import { geometryData } from './d100_geometry.js';
function loadGeometry() {
  // Local ES-module import works from Qt's file:// page without fetch(file://).
  const data = geometryData;
  if (data.faces.length !== 100 || data.faceNumbers.length !== 100 ||
      new Set(data.faceNumbers).size !== 100 ||
      data.faceNumbers.some(n => !Number.isInteger(n) || n < 1 || n > 100)) {
    throw Error('Invalid single-d100 geometry or numbering');
  }
  return Promise.resolve(data);
}

let current = null;
// Return the actual screen-space silhouette of the settled physical d100(s).
// This uses the same camera and world transforms as the 3D renderer, not the
// separate DiceBox canvas (which contains no physical d100 pixels).
export function getPhysicalD100Bounds() {
  if (!current || current.cancelled || typeof current.getBounds !== 'function') return null;
  return current.getBounds();
}
export function clearPhysicalD100() {
  if (!current) return;
  const c = current;
  current = null;
  c.cancelled = true;
  if (c.frame) cancelAnimationFrame(c.frame);
  if (c.disposeScene) c.disposeScene();
  if (c.renderer) {
    c.renderer.dispose();
    c.renderer.forceContextLoss();
  }
  if (c.layer) c.layer.remove();
  if (c.reject) c.reject(new Error('d100 roll cancelled'));
}

function diceFaceLuminance(hex) {
  const match = /^#([0-9a-f]{6})$/i.exec(String(hex || ''));
  if (!match) return 0.4;
  const rgb = [0, 2, 4].map(i => parseInt(match[1].slice(i, i + 2), 16) / 255);
  const linear = rgb.map(n => n <= .04045 ? n / 12.92 : Math.pow((n + .055) / 1.055, 2.4));
  return linear[0] * .2126 + linear[1] * .7152 + linear[2] * .0722;
}

function textureFor(number, renderer, faceColor) {
  const canvas = document.createElement('canvas');
  // Higher-resolution, near-full-face labels remain sharp even when the
  // d100 shares the roller with ordinary dice. 192px keeps GPU use bounded
  // (100 face textures) while improving on the former 160px textures.
  canvas.width = canvas.height = 192;
  const ctx = canvas.getContext('2d');
  ctx.scale(192 / 256, 192 / 256);
  const text = String(number);
  // Clear sans-serif digits occupy more of each face than the old serifs.
  // Fit wide two-/three-digit values to the texture without clipping.
  const targetSize = text.length === 3 ? 175 : text.length === 2 ? 208 : 232;
  const numberFont = 'Arial, Helvetica, sans-serif';
  ctx.font = `900 ${targetSize}px ${numberFont}`;
  const measuredWidth = ctx.measureText(text).width;
  // Keep tall glyphs for 100 / two-digit faces: compress wide numbers only
  // horizontally instead of shrinking the whole font. This uses far more
  // of the small physical d100 face while preserving a safe edge margin.
  const horizontalFit = Math.min(1, 220 / Math.max(1, measuredWidth));
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.lineJoin = 'round';
  const lightInk = diceFaceLuminance(faceColor) < 0.28;
  const ink = lightInk ? '#fffdf5' : '#15131c';
  const outline = lightInk ? '#191522' : '#ffffff';
  // Outer opposite-tone keyline and thicker ink remain visible under both
  // dark and light app themes, including the gold Roll Other Dice d100.
  ctx.strokeStyle = outline;
  ctx.lineWidth = 12;
  ctx.save();
  ctx.translate(128, 130);
  ctx.scale(horizontalFit, 1);
  ctx.strokeText(text, 0, 0);
  ctx.fillStyle = ink;
  ctx.fillText(text, 0, 0);
  ctx.restore();
  if (number === 6 || number === 9) {
    const width = measuredWidth * horizontalFit;
    ctx.fillStyle = ink;
    ctx.fillRect(128 - width * .42, 224, width * .84, 8);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  return texture;
}

// Each die has a separate rigid body and a matching numbered 3D mesh. Numerals
// are immutable children of the mesh, never screen-positioned result overlays.
export async function rollPhysicalD100(quantity, tray, mixed = false, faceColor = '#cb9adb') {
  if (!Number.isInteger(quantity) || quantity < 1 || quantity > 2)
    throw Error('Choose between 1 and 2 physical d100 dice');
  if (!tray) throw Error('Missing dice tray');
  clearPhysicalD100();
  const data = await loadGeometry();
  const layer = document.createElement('div');
  layer.id = 'd100-physics-layer';
  // The tray is already sized and positioned by dice.html. Never overlap
  // DiceBox's separate renderer, including during a mixed d100+ordinary roll.
  layer.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:hidden;background:transparent';
  tray.appendChild(layer);
  const context = {layer, cancelled:false, frame:null, renderer:null, reject:null};
  current = context;
  const radius = Math.max(...data.vertices.map(v => Math.hypot(...v)));
  const spacing = radius * 2 + .3;
  const cols = Math.ceil(Math.sqrt(quantity));
  const rows = Math.ceil(quantity / cols);
  const bound = Math.max(2.5, Math.max(cols, rows) * spacing / 2 + .5);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(quantity > 6 ? 57 : 43, 1, .1, 100);
  camera.up.set(0, 0, -1);
  camera.position.set(0, 13, 0);
  camera.lookAt(0, .6, 0);
  const renderer = new THREE.WebGLRenderer({antialias:true, alpha:true});
  context.renderer = renderer;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0,0);
  renderer.shadowMap.enabled = true;
  const resize = () => {
    const w = Math.max(1, layer.clientWidth), h = Math.max(1, layer.clientHeight);
    if (renderer.domElement.width !== Math.round(w * renderer.getPixelRatio()) ||
        renderer.domElement.height !== Math.round(h * renderer.getPixelRatio())) {
      renderer.setSize(w,h,false);
      camera.aspect=w/h;
      const extent = context.letterExtent || bound + .7;
      if (mixed && quantity === 1) {
        // Mixed rolls have a tall, narrow canvas. The previous framing divided
        // the camera distance by aspect ratio, shrinking one d100 to a speck.
        // Frame it by a stable, pixel-based diameter rather than the WIDTH of
        // the physics arena; the camera tracks its *actual* moving rigid body
        // below so the closer view cannot clip it against the narrow tray.
        const diameterPx = Math.max(40, Math.min(118, w * .72, h * .49));
        const halfFovTan = Math.tan(camera.fov * Math.PI / 360);
        context.mixedCameraDistance = Math.max(
          radius * 3.5,
          radius * h / (diameterPx * halfFovTan)
        );
        // The first animation frame sets the camera on the d100's physics
        // position; this default is only used before that frame is painted.
        camera.position.set(0, context.mixedCameraDistance + 1, 0);
        camera.lookAt(0, 1, 0);
      } else {
        context.mixedCameraDistance = null;
        camera.position.set(0, extent / Math.min(1, camera.aspect) / Math.tan(camera.fov * Math.PI / 360) + radius, 0);
        camera.lookAt(0, 0, 0);
      }
      camera.updateProjectionMatrix();
    }
  };
  layer.appendChild(renderer.domElement);
  // Qt stylesheet forcibly sets canvas dimensions; constrain the physics
  // canvas to its own layer, not to the whole character sheet.
  renderer.domElement.style.cssText = 'display:block;width:100%;height:100%;background:transparent;pointer-events:none';
  resize();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x57647d, 2));
  const light = new THREE.DirectionalLight(0xffffff, 2.7);
  light.position.set(3,9,5);
  light.castShadow = true;
  light.shadow.mapSize.set(1024,1024);
  light.shadow.camera.left = light.shadow.camera.bottom = -8;
  light.shadow.camera.right = light.shadow.camera.top = 8;
  scene.add(light);
  const world = new CANNON.World({gravity:new CANNON.Vec3(0,-20,0)});
  world.solver.iterations=15;
  world.allowSleep=true;
  world.defaultContactMaterial.friction=.90;
  world.defaultContactMaterial.restitution=.09;
  const ground = new CANNON.Body({mass:0,shape:new CANNON.Plane()});
  ground.quaternion.setFromEuler(-Math.PI/2,0,0);
  world.addBody(ground);
  const wallHalf=.26, wallHeight=3.75;
  const barrierMaterial=new CANNON.Material({friction:.75,restitution:.12});
  for (const [x,z,sx,sz] of [
    [bound+wallHalf,0,wallHalf,bound+wallHalf],
    [-bound-wallHalf,0,wallHalf,bound+wallHalf],
    [0,bound+wallHalf,bound+wallHalf,wallHalf],
    [0,-bound-wallHalf,bound+wallHalf,wallHalf]
  ]) {
    const wall = new CANNON.Body({mass:0, material:barrierMaterial,
      shape:new CANNON.Box(new CANNON.Vec3(sx,wallHeight,sz))});
    wall.position.set(x,3.5,z);
    world.addBody(wall);
  }
  const pts = data.vertices.map(v=>new THREE.Vector3(...v));
  const normals = data.faceNormals.map(v=>new THREE.Vector3(...v).normalize());
  const numberTextures = data.faceNumbers.map(n => textureFor(n, renderer, faceColor));
  context.disposeScene = () => {
    // Materials and geometry are shared between dice. Dispose each just once.
    const geometries = new Set(), materials = new Set();
    scene.traverse(node => {
      if (!node.isMesh && !node.isLine) return;
      if (node.geometry) geometries.add(node.geometry);
      if (Array.isArray(node.material)) node.material.forEach(m => materials.add(m));
      else if (node.material) materials.add(node.material);
    });
    geometries.forEach(geometry => geometry.dispose());
    materials.forEach(material => material.dispose());
    numberTextures.forEach(texture => texture.dispose());
  };
  const facePositions=[],labelGeometries=[],labelTransforms=[];
  for (let f=0;f<100;f++) {
    const face=data.faces[f], normal=normals[f];
    const center=new THREE.Vector3();
    for(const idx of face) center.add(pts[idx]);
    center.multiplyScalar(1/face.length);
    const positions=[];
    for(let k=0;k<face.length;k++)
      positions.push(...pts[face[k]].toArray(),...pts[face[(k+1)%face.length]].toArray(),...center.toArray());
    facePositions.push(...positions);
    const u=pts[face[0]].clone().sub(center).normalize();
    const v=new THREE.Vector3().crossVectors(normal,u).normalize();
    let inradius=Infinity;
    for(let k=0;k<face.length;k++) {
      const a=pts[face[k]].clone().sub(center);
      const b=pts[face[(k+1)%face.length]].clone().sub(center);
      const edge=b.clone().sub(a);
      inradius=Math.min(inradius,a.clone().cross(edge).length()/edge.length());
    }
    // Enlarge the label plane but keep all four corners inside each face.
    const side=inradius*Math.SQRT2*.97;
    labelGeometries.push(new THREE.PlaneGeometry(side,side));
    labelTransforms.push({position:center.clone().addScaledVector(normal,.018),
      rotation:new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(u,v,normal))});
  }
  const solidGeometry = new THREE.BufferGeometry();
  solidGeometry.setAttribute('position', new THREE.Float32BufferAttribute(facePositions, 3));
  solidGeometry.computeVertexNormals();
  const solidMaterial = new THREE.MeshStandardMaterial({
    color:faceColor,roughness:.57,metalness:.09,side:THREE.DoubleSide
  });
  const labelMaterials = numberTextures.map(map => new THREE.MeshBasicMaterial({
    map,transparent:true,depthTest:true,depthWrite:false,
    side:THREE.DoubleSide,toneMapped:false
  }));
  const shape=new CANNON.ConvexPolyhedron({
    vertices:data.vertices.map(v=>new CANNON.Vec3(...v)),
    faces:data.faces
  });
  const bodyMaterial=new CANNON.Material({friction:.75,restitution:.10});
  const dieInstances=[];
  for (let i=0;i<quantity;i++) {
    const group=new THREE.Group();
    // One combined solid body instead of 100 separate face draw calls.
    group.add(new THREE.Mesh(solidGeometry, solidMaterial));
    for(let f=0;f<100;f++) {
      const numberMesh=new THREE.Mesh(labelGeometries[f],labelMaterials[f]);
      numberMesh.position.copy(labelTransforms[f].position);
      numberMesh.quaternion.copy(labelTransforms[f].rotation);
      numberMesh.renderOrder=1;
      group.add(numberMesh);
    }
    scene.add(group);
    const body=new CANNON.Body({mass:1,shape,material:bodyMaterial,
      linearDamping:.50,angularDamping:.75,
      allowSleep:true,sleepSpeedLimit:.22,sleepTimeLimit:.7});
    const col=i%cols,row=Math.floor(i/cols);
    body.position.set((col-(cols-1)/2)*spacing,2.6+row*.3,(row-(rows-1)/2)*spacing);
    const q=new THREE.Quaternion().random();
    body.quaternion.set(q.x,q.y,q.z,q.w);
    body.velocity.set((Math.random()-.5)*4,0,(Math.random()-.5)*4);
    body.angularVelocity.set((Math.random()-.5)*16,(Math.random()-.5)*16,(Math.random()-.5)*16);
    world.addBody(body);
    dieInstances.push({group,body,settledFor:0,lastFace:-1,done:false,value:null});
  }
  // Project the real rigid-body mesh vertices onto this engine's canvas.
  // Read only after rendering has settled; the stage can move while rolling.
  context.getBounds = () => {
    if (context.cancelled || !layer.isConnected || !dieInstances.length) return null;
    const rect = renderer.domElement.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return null;
    camera.updateMatrixWorld(true);
    let left=Infinity, top=Infinity, right=-Infinity, bottom=-Infinity;
    const projected = new THREE.Vector3();
    for (const instance of dieInstances) {
      instance.group.updateMatrixWorld(true);
      for (const vertex of pts) {
        projected.copy(vertex).applyMatrix4(instance.group.matrixWorld).project(camera);
        if (!Number.isFinite(projected.x) || !Number.isFinite(projected.y) ||
            projected.z < -1 || projected.z > 1) continue;
        const x=rect.left+(projected.x+1)*rect.width/2;
        const y=rect.top+(1-projected.y)*rect.height/2;
        left=Math.min(left,x); top=Math.min(top,y);
        right=Math.max(right,x); bottom=Math.max(bottom,y);
      }
    }
    if (![left,top,right,bottom].every(Number.isFinite) || right<=left || bottom<=top) return null;
    return {x:left,y:top,width:right-left,height:bottom-top};
  };
  const up=new THREE.Vector3(0,1,0);
  const upwardFace=body=>{
    const q=new THREE.Quaternion(body.quaternion.x,body.quaternion.y,body.quaternion.z,body.quaternion.w);
    let best=-Infinity,index=-1;
    for(let f=0;f<100;f++) {
      const dot=normals[f].clone().applyQuaternion(q).dot(up);
      if(dot>best){best=dot;index=f;}
    }
    return {index,value:data.faceNumbers[index],alignment:best};
  };
  return new Promise((resolve,reject)=>{
    context.reject=reject;
    let last=performance.now(),accumulator=0,elapsed=0;
    const frame=now=>{
      if(context.cancelled)return;
      context.frame=requestAnimationFrame(frame);
      resize();
      accumulator+=Math.min((now-last)/1000,.05);
      last=now;
      let steps=0;
      while(accumulator>=1/120 && steps++<8) {
        world.step(1/120);
        accumulator-=1/120;
        elapsed+=1/120;
        for(const instance of dieInstances) {
          if(instance.done)continue;
          const {body}=instance;
          const candidate=upwardFace(body);
          const grounded=body.position.y<1.25;
          const slow=grounded && body.velocity.length()<.075 && body.angularVelocity.length()<.09;
          instance.settledFor=(slow && candidate.index===instance.lastFace)
            ? instance.settledFor+1/120 : 0;
          instance.lastFace=candidate.index;
          if(grounded && elapsed>1 && (body.sleepState===CANNON.Body.SLEEPING || instance.settledFor>1)) {
            instance.value=candidate.value;
            instance.done=true;
            body.velocity.setZero();body.angularVelocity.setZero();
            body.sleep();
            const outlinePoints=data.faces[candidate.index].map(idx=>
              pts[idx].clone().addScaledVector(normals[candidate.index],.022));
            const outline=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(outlinePoints),
              new THREE.LineBasicMaterial({color:'#ffec87',depthTest:false}));
            outline.renderOrder=999;
            instance.group.add(outline);
          }
        }
      }
      if(steps>8)accumulator=0;
      for(const instance of dieInstances) {
        instance.group.position.copy(instance.body.position);
        instance.group.quaternion.copy(instance.body.quaternion);
      }
      if (mixed && quantity === 1 && context.mixedCameraDistance) {
        // The d100 can bounce laterally and vertically while the cameras for
        // ordinary dice run independently. Follow its physical position with
        // a damped target so it stays fully visible without fake repositioning
        // or altering any of its rigid-body motion / final result.
        const bodyPosition = dieInstances[0].body.position;
        const target = new THREE.Vector3(bodyPosition.x, bodyPosition.y, bodyPosition.z);
        if (!context.mixedCameraFocus) context.mixedCameraFocus = target.clone();
        else context.mixedCameraFocus.lerp(target, .35);
        const focus = context.mixedCameraFocus;
        camera.position.set(focus.x, focus.y + context.mixedCameraDistance, focus.z);
        camera.lookAt(focus);
      }
      renderer.render(scene,camera);
      if(dieInstances.every(instance=>instance.done)) {
        cancelAnimationFrame(context.frame);
        context.frame=null;
        context.reject=null;
        resolve(dieInstances.map(instance=>instance.value));
      } else if(elapsed>15+quantity*.75) {
        cancelAnimationFrame(context.frame);
        context.frame=null;
        context.reject=null;
        reject(new Error('Physical d100 did not settle; no substitute result generated'));
      }
    };
    context.frame=requestAnimationFrame(frame);
  });
}
