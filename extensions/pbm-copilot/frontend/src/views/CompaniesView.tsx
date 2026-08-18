import React, { useCallback, useEffect, useState } from 'react';
import { Table, Button, Alert, Space } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { getCompanies, Company } from '../api';

const CompaniesView: React.FC = () => {
  const [rows, setRows] = useState<Company[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  const load = useCallback(async () => {
    setLoading(true);
    setError(undefined);
    try {
      setRows(await getCompanies());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load companies');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const columns: ColumnsType<Company> = [
    { title: 'Company', dataIndex: 'name', key: 'name' },
    { title: 'Company ID', dataIndex: 'company_id', key: 'company_id' },
    {
      title: 'Rows',
      dataIndex: 'record_count',
      key: 'record_count',
      align: 'right',
      render: (v: number) => v.toLocaleString(),
    },
    {
      title: 'Uploaded',
      dataIndex: 'uploaded_at',
      key: 'uploaded_at',
      render: (v: string) => new Date(v).toLocaleString(),
    },
    { title: 'Status', dataIndex: 'status', key: 'status' },
    {
      title: 'Dashboard',
      key: 'dashboard',
      render: (_, row) =>
        row.dashboard_url ? (
          <a href={row.dashboard_url} target="_blank" rel="noreferrer">
            Open
          </a>
        ) : (
          '—'
        ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
        Refresh
      </Button>
      {error && <Alert type="error" showIcon message={error} />}
      <Table
        rowKey="company_id"
        columns={columns}
        dataSource={rows}
        loading={loading}
        size="small"
        pagination={{ pageSize: 10 }}
      />
    </Space>
  );
};

export default CompaniesView;