import React, { useEffect, useState } from 'react';
import { Tabs, Alert, Button, Typography } from 'antd';
import {
  ApiOutlined,
  CloudUploadOutlined,
  DatabaseOutlined,
  AlertOutlined,
  MessageOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { getConfig } from './api';
import UploadView from './views/UploadView';
import CompaniesView from './views/CompaniesView';
import AnomaliesView from './views/AnomaliesView';
import ExplainView from './views/ExplainView';
import SettingsView from './views/SettingsView';

const CopilotPanel: React.FC = () => {
  const [connection, setConnection] = useState<
    { ok: boolean; message: string } | undefined
  >(undefined);
  const [checking, setChecking] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    setChecking(true);
    setConnection(undefined);
    getConfig()
      .then((cfg) => {
        setConnection({
          ok: true,
          message: `Connected to ${cfg.service} v${cfg.version}${
            cfg.auth_required ? ' (token required)' : ''
          }`,
        });
      })
      .catch((err: Error) => {
        setConnection({ ok: false, message: err.message });
      })
      .finally(() => setChecking(false));
  }, [refreshKey]);

  const items = [
    {
      key: 'upload',
      label: (
        <span>
          <CloudUploadOutlined /> Upload
        </span>
      ),
      children: <UploadView />,
    },
    {
      key: 'companies',
      label: (
        <span>
          <DatabaseOutlined /> Companies
        </span>
      ),
      children: <CompaniesView />,
    },
    {
      key: 'anomalies',
      label: (
        <span>
          <AlertOutlined /> Anomalies
        </span>
      ),
      children: <AnomaliesView />,
    },
    {
      key: 'explain',
      label: (
        <span>
          <MessageOutlined /> Explain
        </span>
      ),
      children: <ExplainView />,
    },
    {
      key: 'settings',
      label: (
        <span>
          <SettingOutlined /> Settings
        </span>
      ),
      children: (
        <SettingsView onSaved={() => setRefreshKey((k) => k + 1)} />
      ),
    },
  ];

  return (
    <div
      className="pbm-copilot-panel"
      style={{
        padding: 16,
        height: '100%',
        overflow: 'auto',
      }}
    >
      <style>{`
        .pbm-copilot-panel .ant-tabs-content-holder {
          height: auto !important;
        }
        .pbm-copilot-panel .ant-tabs-content {
          height: auto !important;
          overflow: visible !important;
        }
        .pbm-copilot-panel .ant-tabs-content > .ant-tabs-tabpane {
          position: static !important;
          inset: auto !important;
        }
      `}</style>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        PBM Claims Anomaly &amp; Compliance Copilot
      </Typography.Title>
      {checking ? null : connection && !connection.ok ? (
        <Alert
          type="error"
          showIcon
          message="Cannot reach the PBM API"
          description={
            <span>
              {connection.message}. Open the <b>Settings</b> tab to set the API base
              URL and token.
            </span>
          }
          action={
            <Button size="small" onClick={() => window.location.reload()}>
              Retry
            </Button>
          }
          style={{ marginBottom: 12 }}
        />
      ) : connection ? (
        <Alert
          type="success"
          showIcon
          icon={<ApiOutlined />}
          message={connection.message}
          style={{ marginBottom: 12 }}
        />
      ) : null}
      <Tabs items={items} style={{ minHeight: 500 }} />
    </div>
  );
};

export default CopilotPanel;