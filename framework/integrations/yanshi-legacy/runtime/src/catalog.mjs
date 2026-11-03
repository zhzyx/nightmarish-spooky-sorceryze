// Stages describe capabilities, never a permanent roster of agents.
export const stages = [
  ['planning', '策划文档', ['gameplay', 'full'], ['目标玩家、核心循环、范围与验收标准', '玩法规则、数值假设及风险']],
  ['interaction', '交互设计', ['ui', 'gameplay', 'full'], ['操作流程、状态及异常路径', '输入设备、可访问性及交互原型']],
  ['visual', '视觉设计', ['art', 'ui', 'character', 'scene', 'full'], ['视觉规范、参考来源与授权', '色彩、材质、风格一致性']],
  ['model', '模型设计', ['character', 'scene', 'full'], ['比例、拓扑、UV、LOD、骨骼及碰撞约束', '引擎格式、尺度和预算']],
  ['motion_vfx', '动效及特效资产评估', ['animation', 'vfx', 'character', 'full'], ['动作列表、重定向、根运动、特效时序', '兼容性、授权、GPU与内存预算']],
  ['terrain_level', '3D地形及关卡场景评估', ['level', 'scene', 'full'], ['白盒、动线、导航、碰撞与可达性', '地形、光照、流式加载及性能预算']],
  ['assets', '角色及场景资产落地', ['art', 'character', 'scene', 'animation', 'vfx', 'level', 'full'], ['源文件、导入设置、材质及依赖清单', '来源授权、哈希、LOD与预算实测']],
  ['integration', '程序逻辑接入', ['code', 'bug', 'gameplay', 'ui', 'art', 'character', 'scene', 'animation', 'vfx', 'level', 'full'], ['接口、事件、数据结构及错误处理', '资产引用与逻辑集成证据']],
  ['runtime', '运行及调试', ['code', 'bug', 'gameplay', 'ui', 'art', 'character', 'scene', 'animation', 'vfx', 'level', 'full'], ['引擎版本、平台、构建命令、运行日志', '玩法复现、帧耗时、内存与异常证据']],
  ['evaluation', 'Bug检索及产出评价', ['always'], ['复现步骤、期望与实际、严重度及回归证据', '功能、视觉、交互、性能、授权的评价与未知项']],
  ['retrospective', '复盘及流程优化', ['always'], ['工单、事件、产物及验收证据汇总', '问题根因、改进假设、适用范围与回滚条件']]
].map(([id, name, triggers, acceptance]) => ({ id, name, triggers, acceptance }));
export const changeTypes = [...new Set(stages.flatMap(s => s.triggers))].filter(x => x !== 'always').concat('docs');

export function route(request) {
  if (!request.title || !request.goal || !Array.isArray(request.changes) || !request.changes.length)
    throw Error('需求必须包含 title、goal 和非空 changes');
  for (const c of request.changes) if (!changeTypes.includes(c)) throw Error(`未知变化类型: ${c}`);
  for (const [id, choice] of Object.entries(request.overrides || {})) {
    if (!stages.some(s => s.id === id) || typeof choice.include !== 'boolean' || !choice.reason)
      throw Error('阶段覆写必须提供有效阶段、include 和 reason');
    if (['evaluation', 'retrospective'].includes(id) && !choice.include) throw Error('评价与复盘不可省略，可缩小范围');
  }
  return stages.map(s => {
    const override = request.overrides?.[s.id];
    const matches = s.triggers.filter(t => t === 'always' || request.changes.includes(t));
    return { ...s, include: override ? override.include : matches.length > 0,
      reason: override?.reason || (matches.length ? `需求变化: ${matches.join(', ')}` : '本需求未涉及此能力') };
  });
}
