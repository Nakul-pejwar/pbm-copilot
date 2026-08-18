import React from 'react';
import { views } from '@apache-superset/core';
import CopilotPanel from './CopilotPanel';

views.registerView(
  { id: 'pbm.pbm-copilot.main', name: 'PBM Copilot' },
  'sqllab.panels',
  () => <CopilotPanel />,
);