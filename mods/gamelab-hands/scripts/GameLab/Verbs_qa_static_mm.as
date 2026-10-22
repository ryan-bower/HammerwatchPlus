// Bounded original-code neighbor: actual MM input, then actual noncritical TT input.
// Reads normal HP/crit text/projectiles/stacks. No damage/event/stack hooks or setters.
namespace GameLab
{
 const string QA_STATIC_MM_PROJECTILE = "players/wizard/projectiles/magic_missile_seeking.unit";
 class QAStaticMMTask : QAStaticObserveTask
 {
  int m_firstAt = -1, m_ttProducerAt = -1, m_lateAt = -1;
  double m_initialHp = 0, m_preTTHp = 0;
  int CountOwned(const string &in path)
  {
   auto producer = Resources::GetUnitProducer(path);
   if (producer is null) return 0;
   auto units = g_scene.FetchAllUnitsOfType(producer);
   int count = 0;
   if (units.length()>32)m_truncated=true;
   for (uint i=0;i<units.length() && i<32;i++)
   {
    if (!units[i].IsValid() || units[i].IsDestroyed()) continue;
    auto projectile = cast<NewProjectile>(units[i].GetScriptBehavior());
    if (projectile !is null && projectile.m_owner is m_player) count++;
   }
   return count;
  }
  string MMProjectiles()
  {
   array<string> rows;
   array<string> paths = { QA_STATIC_MM_PROJECTILE, QA_STATIC_PROJECTILE };
   for (uint k=0;k<paths.length();k++)
   {
    auto producer = Resources::GetUnitProducer(paths[k]);
    if (producer is null) continue;
    auto units = g_scene.FetchAllUnitsOfType(producer);
    if (units.length()>32)m_truncated=true;
    for (uint i=0;i<units.length() && i<32;i++)
    {
     if (!units[i].IsValid() || units[i].IsDestroyed()) continue;
     auto projectile = cast<NewProjectile>(units[i].GetScriptBehavior());
     if (projectile is null || projectile.m_owner !is m_player) continue;
     if (rows.length()>=8) { m_truncated=true; break; }
     vec3 pos = units[i].GetPosition();
     Json row;
     row.Str("kind", k==0 ? "MM" : "TT").Int("unit",units[i].GetId())
      .Int("owner",m_player.m_unit.GetId()).Num("x",pos.x).Num("y",pos.y);
     rows.insertLast(row.Close());
    }
   }
   return RawArray(rows);
  }
  int LatestCrit(int now)
  {
   int latest=-1;
   for (uint i=0;i<g_floatingTexts.length();i++)
   {
    auto f=g_floatingTexts[i];
    if (f !is null && f.m_alive && f.m_type==FloatingTextType::EnemyImmortal
      && QAStaticCritText(f.m_floatingText)) latest=max(latest,now-f.m_timeLived);
   }
   return latest;
  }
  double TargetHp()
  {
   double hp=0;
   for (uint i=0;i<m_targets.length();i++)
   {
    auto a=m_targets[i];
    if (!a.m_unit.IsValid() || a.m_unit.IsDestroyed() || a.IsDead())return -1;
    hp+=double(a.GetHealth())*double(a.GetMaxHp());
   }
   return hp;
  }
  void MMPhase(const string &in name)
  {
   int now=int(g_scene.GetTime());
   Json row;
   row.Str("phase",name).Int("t",m_t).Int("now",now).Int("stacks",m_player.GetStacks(m_stacks))
    .Raw("targets",TargetRows()).Raw("crits",CritRows(now)).Raw("projectiles",MMProjectiles())
    .Int("tt_cd",QAStaticCooldown(m_tt)).Int("mm_cd",QAStaticCooldown(m_mm))
    .Num("tt_crit",m_tt.m_modCritChance).Num("mm_crit",m_mm.m_modCritChance)
    .Num("spell_crit",m_player.m_record.currStats.SpellCritChance)
    .Num("mana",m_player.m_record.mana*float(m_player.m_record.MaxMana()));
   string payload=row.Close();m_phases.insertLast(payload);
   Json ev;Emit(ev.Str("ev","qa_static_mm_phase").Str("tag",m_tag).Raw("data",payload));
  }
  void MMFinish(bool complete,const string &in error)
  {
   g_qaStaticBusy=false;
   for (uint start=0;start<m_samples.length();start+=16)
   {
    array<string> part;
    for (uint i=start;i<m_samples.length() && i<start+16;i++)part.insertLast(m_samples[i]);
    Json chunk;Emit(chunk.Str("ev","qa_static_mm_samples").Str("tag",m_tag).Int("offset",int(start)).Raw("samples",RawArray(part)));
   }
   Json ev;
   Emit(ev.Str("ev","qa_static_mm_observe").Str("tag",m_tag).Bool("complete",complete).Str("error",error)
    .Int("ms",m_t).Int("frames",m_frames).Int("sample_count",int(m_samples.length())).Int("phase_count",int(m_phases.length()))
    .Bool("truncated",m_truncated).Int("mm_input_at",m_mmAt).Int("tt_input_at",m_ttAt)
    .Int("first_crit_at",m_firstAt).Int("tt_producer_at",m_ttProducerAt).Int("late_crit_at",m_lateAt)
    .Int("mm_input_frames",m_ttInputFrames).Int("tt_input_frames",m_ttAt>=0 ? int(g_held.frames) : 0)
    .Int("held_ms_left",g_held.msLeft).Bool("releasing",Releasing()));
  }
  bool UpdateFrame(int ms) override
  {
   m_t+=ms;m_frames++;
   if (ms<=0 || ms>100 || m_player is null || !m_player.m_unit.IsValid() || m_player.IsDead() || GetLocalPlayer() !is m_player)
   { MMFinish(false,"native frame/local actor invalid");return true; }
   if (dist(m_origin,xy(m_player.m_unit.GetPosition()))>2 || TargetHp()<=0)
   { MMFinish(false,"fixture actor moved/target invalid");return true; }
   int now=int(g_scene.GetTime());
   if (m_mmAt<0)
   {
    MMPhase("before_mm");m_mmAt=now;m_initialHp=TargetHp();
    array<string> buttons={m_mmButton};Hold(m_tag+".mm",200,vec2(),true,m_direction,buttons);
   }
   int latest=LatestCrit(now);
   if (m_firstAt<0 && latest>=m_mmAt-33 && TargetHp()<m_initialHp-0.1 && m_player.GetStacks(m_stacks)==2)
   { m_firstAt=now;MMPhase("first_mm_crit"); }
   if (m_ttAt<0 && m_firstAt>=0 && m_t>=300 && g_held.msLeft<=0 && !Releasing())
   {
    MMPhase("before_tt");m_preTTHp=TargetHp();m_ttInputFrames=int(g_held.frames);m_ttAt=now;
    array<string> buttons={m_ttButton};Hold(m_tag+".tt",200,vec2(),true,vec2(-m_direction.x,-m_direction.y),buttons);
   }
   if (m_ttAt>=0 && m_ttProducerAt<0 && CountOwned(QA_STATIC_PROJECTILE)==1)
   { m_ttProducerAt=now;MMPhase("actual_tt"); }
   if (m_lateAt<0 && m_ttProducerAt>=0 && latest>m_ttProducerAt+67 && TargetHp()<m_preTTHp-0.1)
   { m_lateAt=now;MMPhase("late_mm_crit"); }
   Json sample;
   sample.Int("t",m_t).Int("now",now).Int("stacks",m_player.GetStacks(m_stacks)).Num("hp",TargetHp())
    .Int("tt_cd",QAStaticCooldown(m_tt)).Int("mm_cd",QAStaticCooldown(m_mm)).Int("latest_crit_birth",latest)
    .Int("mm_live",CountOwned(QA_STATIC_MM_PROJECTILE)).Int("tt_live",CountOwned(QA_STATIC_PROJECTILE));
   if (m_samples.length()<200)m_samples.insertLast(sample.Close());else m_truncated=true;
   if (m_t<4000)return false;
   MMPhase("finished");MMFinish(true,"");return true;
  }
 }
 void VerbQAStaticMM(const string &in id,array<string>@ args)
 {
  auto plr=cast<PlayerBase>(GetLocalPlayer());
  if (plr is null || args.length()!=3 || g_qaStaticBusy || QueuedTasks::g_instance is null)
  { Fail(id,"needs local player, idle task and <tag> <aimX> <aimY>");return; }
  auto tt=QAStaticSkill(plr,QA_STATIC_TT);auto mm=QAStaticSkill(plr,QA_STATIC_MM);auto sc=QAStaticSkill(plr,QA_STATIC_SC);
  auto stacks=ActorBuffStackDef::Get("players/hwp/specs/stacks_specs.sval:static_charge");
  vec2 direction(parseFloat(args[1]),parseFloat(args[2]));
  if (tt is null || mm is null || sc is null || stacks is null || length(direction)<0.5f
    || g_held.msLeft>0 || Releasing() || plr.GetStacks(stacks)!=0 || QAStaticCooldown(tt)>0 || QAStaticCooldown(mm)>0
    || tt.m_modCritChance!=0 || mm.m_modCritChance!=1 || plr.m_record.currStats.SpellCritChance!=0 || plr.m_record.CurrentMana()<80)
  { Fail(id,"requires ready released TT/MM, zero stacks, MMcrit1/TTglobalcrit0 and mana80");return; }
  QAStaticMMTask task;task.m_tag=args[0];@task.m_player=plr;@task.m_tt=tt;@task.m_mm=mm;@task.m_stacks=stacks;
  task.m_origin=xy(plr.m_unit.GetPosition());task.m_direction=normalize(direction);
  task.m_ttButton=SkillButton(plr,tt);task.m_mmButton=SkillButton(plr,mm);
  auto producer=Resources::GetUnitProducer(QA_STATIC_TARGET);
  if (producer !is null)
  {
   auto units=g_scene.FetchAllUnitsOfType(producer);
   for (uint i=0;i<units.length();i++)
   {
    if (!units[i].IsValid() || units[i].IsDestroyed())continue;
    auto a=cast<Actor>(units[i].GetScriptBehavior());
    if (a !is null && !a.IsDead() && dist(task.m_origin,xy(units[i].GetPosition()))<=150)task.m_targets.insertLast(a);
   }
  }
  bool targetsValid=task.m_targets.length()==3;
  for (uint i=0;i<task.m_targets.length();i++)targetsValid=targetsValid && task.m_targets[i].GetMaxHp()==15000 && task.m_targets[i].GetHealth()==1;
  if (!targetsValid
    || task.m_ttButton=="" || task.m_mmButton=="" || task.m_ttButton==task.m_mmButton
    || task.CountOwned(QA_STATIC_MM_PROJECTILE)!=0 || task.CountOwned(QA_STATIC_PROJECTILE)!=0 || task.LatestCrit(int(g_scene.GetTime()))>=0)
  { Fail(id,"requires three fresh15k targets, distinct native bindings and no old own projectiles/critical texts");return; }
  g_qaStaticBusy=true;QueuedTasks::Queue(task);
  Emit(Reply(id,true).Str("tag",task.m_tag).Int("ms",4000).Str("mm_button",task.m_mmButton).Str("tt_button",task.m_ttButton));
 }
 void Register_qa_static_mm() { RegisterVerb("qa_static_mm","<tag> <aimX> <aimY>",Verb(VerbQAStaticMM)); }
}
