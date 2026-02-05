import { useState } from 'react';
import { Tab } from '@headlessui/react';
import {
  ShieldCheckIcon,
  DocumentTextIcon,
  CloudArrowUpIcon,
  ClipboardDocumentCheckIcon,
  ChartBarIcon
} from '@heroicons/react/24/outline';
import {
  ComplianceDashboard,
  DynamicJobForm,
  DocumentUpload,
  ContractReadinessChecker,
  ComplianceReport
} from '../components/compliance';

function classNames(...classes) {
  return classes.filter(Boolean).join(' ');
}

export default function Compliance() {
  const [selectedTab, setSelectedTab] = useState(0);

  const tabs = [
    { name: 'Dashboard', icon: ShieldCheckIcon, component: <ComplianceDashboard /> },
    { name: 'Documents', icon: CloudArrowUpIcon, component: <DocumentUpload /> },
    { name: 'Contract Readiness', icon: ClipboardDocumentCheckIcon, component: <ContractReadinessChecker /> },
    { name: 'Reports', icon: ChartBarIcon, component: <ComplianceReport /> }
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <Tab.Group selectedIndex={selectedTab} onChange={setSelectedTab}>
        <Tab.List className="flex space-x-1 rounded-xl bg-green-900/10 p-1">
          {tabs.map((tab) => (
            <Tab
              key={tab.name}
              className={({ selected }) =>
                classNames(
                  'w-full rounded-lg py-2.5 text-sm font-medium leading-5',
                  'ring-white ring-opacity-60 ring-offset-2 ring-offset-green-400 focus:outline-none focus:ring-2',
                  selected
                    ? 'bg-white shadow text-green-700'
                    : 'text-gray-600 hover:bg-white/[0.12] hover:text-green-600'
                )
              }
            >
              <div className="flex items-center justify-center">
                <tab.icon className="h-5 w-5 mr-2" />
                {tab.name}
              </div>
            </Tab>
          ))}
        </Tab.List>
        <Tab.Panels className="mt-6">
          {tabs.map((tab, idx) => (
            <Tab.Panel
              key={idx}
              className={classNames(
                'rounded-xl',
                'ring-white ring-opacity-60 ring-offset-2 ring-offset-green-400 focus:outline-none'
              )}
            >
              {tab.component}
            </Tab.Panel>
          ))}
        </Tab.Panels>
      </Tab.Group>
    </div>
  );
}
