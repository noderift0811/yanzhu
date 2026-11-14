import { useEffect, useState } from "react";
import { Button, Card, Modal, Tag, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";
import { request } from "../lib/api.js";
import { chooseScene, formatSwitchAt, useMe } from "../lib/me.js";

// 选场景 / 换场景。两个状态共用一页：
// - 没选过 = 引导（不可跳过，一次选定 30 天内可改一次）
// - 选过 = 锁定视图（当前场景高亮，其余需确认且受冷却）
export default function ScenePage() {
  const navigate = useNavigate();
  const me = useMe();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(null); // { scene, isSwitch }
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    request("/meta/presets", { auth: false })
      .then((d) => live && setItems(d.items || []))
      .catch((e) => message.error(e.message))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, []);

  const chosen = me?.scene_chosen === true;
  // 未选场景时后端会回落 free，但那是兜底值、不是"已选"——高亮它会让引导页一开始就像选好了
  const current = chosen ? me?.scene_id : null;

  const pick = (p, locked) => {
    if (p.id === current) return;
    if (locked) {
      message.info(
        `${formatSwitchAt(me?.next_switch_at) || "冷却期结束后"}才能换场景，当前锁定在「${
          me?.scene_name || ""
        }」`
      );
      return;
    }
    setPending({ scene: p, isSwitch: chosen });
  };

  const confirm = async () => {
    if (!pending) return;
    setBusy(true);
    try {
      const data = await chooseScene(pending.scene.id, pending.isSwitch);
      setPending(null);
      message.success(
        data.switched
          ? `已切换到「${data.scene_name}」，原场景的 ${data.archived_personas} 个人格已归档`
          : `已选定「${data.scene_name}」`
      );
      navigate("/", { replace: true });
    } catch (e) {
      message.error(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="pf-scene">
      <div className="pf-scene-inner">
        <div className="pf-scene-brand">
          <span className="pf-brand-mark">言</span>
          <span className="pf-scene-brand-name">言筑</span>
        </div>
        <Typography.Title level={3} className="pf-scene-title">
          {chosen ? `当前场景：${me?.scene_name || ""}` : "先选一个场景"}
        </Typography.Title>
        <Typography.Paragraph type="secondary" className="pf-scene-sub">
          {chosen
            ? me?.can_switch
              ? "场景决定检索语料与安全边界。切换会把当前场景下的人格归档（不删除），可以再翻出来看。"
              : `这个账号已锁定在「${me?.scene_name || ""}」，${
                  formatSwitchAt(me?.next_switch_at) || "冷却期结束后"
                }可再切换一次。`
            : "一个账号只做一件事：选定的场景决定 AI 用哪套语料、守哪套边界、默认长什么样。选定后 30 天内可改一次。"}
        </Typography.Paragraph>
        {me?.is_demo && (
          <div className="pf-scene-demo">
            演示账号不受切换冷却限制，可以逐个场景验证；正式注册的账号按上方规则执行。
          </div>
        )}

        <div className="pf-scene-grid">
          {items.map((p) => {
            const on = p.id === current;
            const locked = chosen && !me?.can_switch && !me?.is_demo && !on;
            return (
              <Card
                key={p.id}
                className={`pf-scene-card${on ? " is-on" : ""}${locked ? " is-locked" : ""}`}
                onClick={() => pick(p, locked)}
                hoverable={!locked && !on}
              >
                <span className="pf-scene-bar" style={{ background: p.accent }} />
                <div className="pf-scene-head">
                  <span className="pf-scene-name">{p.name}</span>
                  {on && <Tag color="green">当前</Tag>}
                  {locked && <Tag>冷却中</Tag>}
                </div>
                <div className="pf-scene-subtitle">{p.subtitle}</div>
                <ul className="pf-scene-points">
                  {(p.highlights || []).map((h) => (
                    <li key={h}>{h}</li>
                  ))}
                </ul>
                <div className="pf-scene-tags">
                  {(p.tags || []).slice(0, 4).map((t) => (
                    <Tag key={t}>{t}</Tag>
                  ))}
                  {!p.tags?.length && <span className="pf-scene-empty">不限标签</span>}
                </div>
              </Card>
            );
          })}
        </div>

        {!loading && !chosen && (
          <Typography.Paragraph type="secondary" className="pf-scene-foot">
            选定后会直接进入工作台；想改主意只有一个入口——本页。
          </Typography.Paragraph>
        )}
        {chosen && (
          <Button className="pf-scene-back" onClick={() => navigate("/", { replace: true })}>
            返回工作台
          </Button>
        )}
      </div>

      <Modal
        open={!!pending}
        title={pending?.isSwitch ? `切换到「${pending.scene.name}」？` : `选定「${pending?.scene.name || ""}」？`}
        okText={pending?.isSwitch ? "确认切换" : "就选它"}
        cancelText="再看看"
        confirmLoading={busy}
        onOk={confirm}
        onCancel={() => setPending(null)}
      >
        {pending?.isSwitch ? (
          <>
            <p>
              当前场景「{me?.scene_name}」下的所有人格会归档为只读，不会删除，但不再出现在列表里。
            </p>
            <p className="pf-scene-modal-warn">
              切换后 30 天内不能再改（演示账号除外）。
            </p>
          </>
        ) : (
          <>
            <p>这个账号之后只在这个场景里生成人格：检索语料、安全边界、默认骨架都按它来。</p>
            <p className="pf-scene-modal-warn">选定后 30 天内可改一次，改的时候旧人格会归档。</p>
          </>
        )}
      </Modal>
    </div>
  );
}
