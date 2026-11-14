import { useEffect, useState } from "react";
import { Button, Card, Form, Input, Tabs, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";
import { authStore, bootstrapAuth, request } from "../lib/api.js";

// 登录 / 注册（成功即发双令牌：access 内存 + refresh localStorage）
export default function LoginPage() {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [tab, setTab] = useState("login");
  const [loading, setLoading] = useState(false);
  const [demo, setDemo] = useState(null);

  useEffect(() => {
    let live = true;
    bootstrapAuth().then((ok) => {
      if (ok && live) navigate("/", { replace: true });
    });
    // 演示账号由后端下发（DEMO_USER_ENABLED=false 时 enabled=false，入口自动隐藏）
    request("/meta/demo-account", { auth: false })
      .then((data) => live && setDemo(data))
      .catch(() => live && setDemo({ enabled: false }));
    return () => {
      live = false;
    };
  }, [navigate]);

  const fillDemo = () => {
    setTab("login");
    form.setFieldsValue({ username: demo.username, password: demo.password });
    message.success("已填入演示账号");
  };

  const onFinish = async (values) => {
    setLoading(true);
    try {
      const data = await request(`/auth/${tab === "login" ? "login" : "register"}`, {
        method: "POST",
        body: values,
        auth: false,
      });
      authStore.setTokens(data.access_token, data.refresh_token);
      navigate("/", { replace: true });
    } catch (e) {
      message.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="pf-auth">
      <Card className="pf-auth-card">
        <Typography.Title level={3} className="pf-auth-title">
          言筑
        </Typography.Title>
        <Typography.Paragraph type="secondary">
          说出几个人格限定词，AI 把它们筑成一个能对话的人
        </Typography.Paragraph>
        <Tabs
          activeKey={tab}
          onChange={setTab}
          items={[
            { key: "login", label: "登录" },
            { key: "register", label: "注册" },
          ]}
        />
        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          initialValues={{ username: "", password: "" }}
        >
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: "请输入用户名" },
              { min: 3, max: 20, message: "3-20 位字母、数字、下划线或中文" },
            ]}
          >
            <Input placeholder="3-20 位" autoComplete="username" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: "请输入密码" },
              { min: 6, max: 64, message: "6-64 位" },
            ]}
          >
            <Input.Password placeholder="至少 6 位" autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            {tab === "login" ? "登录" : "注册并进入"}
          </Button>
        </Form>
        {demo?.enabled ? (
          <div className="pf-demo-account">
            <div className="pf-demo-text">
              <span className="pf-demo-label">演示账号</span>
              <span className="pf-demo-cred">
                <code>{demo.username}</code>
                <span className="pf-demo-sep">/</span>
                <code>{demo.password}</code>
              </span>
            </div>
            <Button size="small" onClick={fillDemo}>
              一键填充
            </Button>
          </div>
        ) : null}
      </Card>
    </div>
  );
}
