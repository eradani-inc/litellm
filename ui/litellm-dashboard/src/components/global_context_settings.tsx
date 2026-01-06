import React, { useEffect, useState } from "react";
import { Card, Text, Title } from "@tremor/react";
import { Button, Form, Input, message, Spin, Typography } from "antd";
import { getGlobalContext, setGlobalContext } from "./networking";

const { TextArea } = Input;
const { Paragraph } = Typography;

interface GlobalContextSettingsProps {
  accessToken: string | null;
}

const GlobalContextSettings: React.FC<GlobalContextSettingsProps> = ({ accessToken }) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [currentContext, setCurrentContext] = useState<string>("");

  useEffect(() => {
    const fetchContext = async () => {
      if (!accessToken) return;
      
      try {
        setLoading(true);
        const data = await getGlobalContext(accessToken);
        setCurrentContext(data.global_context || "");
        form.setFieldsValue({
          system_prompt: data.global_context || ""
        });
      } catch (error) {
        console.error("Failed to fetch global context:", error);
        message.error("Failed to load global context settings");
      } finally {
        setLoading(false);
      }
    };

    fetchContext();
  }, [accessToken, form]);

  const handleSave = async (values: { system_prompt: string }) => {
    if (!accessToken) return;

    try {
      setSaving(true);
      await setGlobalContext(accessToken, values.system_prompt);
      setCurrentContext(values.system_prompt);
      message.success("Global context updated successfully");
    } catch (error) {
      console.error("Failed to save global context:", error);
      message.error("Failed to save global context");
    } finally {
      setSaving(false);
    }
  };

  const handleClear = async () => {
    if (!accessToken) return;

    try {
      setSaving(true);
      await setGlobalContext(accessToken, "");
      setCurrentContext("");
      form.setFieldsValue({ system_prompt: "" });
      message.success("Global context cleared");
    } catch (error) {
      console.error("Failed to clear global context:", error);
      message.error("Failed to clear global context");
    } finally {
      setSaving(false);
    }
  };

  if (!accessToken) {
    return null;
  }

  return (
    <div className="p-4">
      <Card>
        <Title>Global System Prompt / Context</Title>
        <Text className="mb-4">
          Configure a system prompt that will be automatically prepended to all API requests. 
          This is useful for setting organization-wide instructions, guidelines, or context 
          that should be included in every conversation.
        </Text>
        
        <Paragraph type="secondary" className="mb-4">
          <strong>How it works:</strong> When a request is made to the API, this system prompt 
          will be automatically added as the first message (with role &quot;system&quot;) before 
          any user-provided messages. If the request already has a system message, this global 
          context will be prepended to it.
        </Paragraph>

        {loading ? (
          <div className="flex justify-center py-8">
            <Spin size="large" />
          </div>
        ) : (
          <Form
            form={form}
            onFinish={handleSave}
            layout="vertical"
            initialValues={{ system_prompt: currentContext }}
          >
            <Form.Item
              name="system_prompt"
              label="System Prompt"
              help="Enter the system prompt or context you want to prepend to all requests"
            >
              <TextArea
                rows={8}
                placeholder="Enter your global system prompt here...

Example:
You are a helpful AI assistant for Acme Corporation. Always be professional, accurate, and helpful. Follow these guidelines:
- Be concise and clear in your responses
- If you're unsure about something, say so
- Always prioritize user safety and data privacy"
                className="font-mono"
              />
            </Form.Item>

            <div className="flex gap-2">
              <Button type="primary" htmlType="submit" loading={saving}>
                Save Changes
              </Button>
              <Button onClick={handleClear} loading={saving} danger>
                Clear Context
              </Button>
            </div>
          </Form>
        )}

        {currentContext && (
          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <Text className="font-medium">Current Active Context:</Text>
            <pre className="mt-2 p-3 bg-white rounded border text-sm overflow-auto max-h-40">
              {currentContext}
            </pre>
          </div>
        )}
      </Card>
    </div>
  );
};

export default GlobalContextSettings;
