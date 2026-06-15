'use client';

import { useState } from 'react';
import { Folder, FolderOpen, File, FileCode } from 'lucide-react';
import type { StudioFileNode } from '@/lib/api/studio';

interface TreeNode {
  name: string;
  path: string;
  fileId?: number;
  children: Record<string, TreeNode>;
}

function buildTree(files: StudioFileNode[]): Record<string, TreeNode> {
  const root: Record<string, TreeNode> = {};
  for (const file of files) {
    const parts = file.path.split('/');
    let current = root;
    parts.forEach((part, i) => {
      if (!current[part]) {
        current[part] = { name: part, path: parts.slice(0, i + 1).join('/'), children: {} };
      }
      if (i === parts.length - 1) {
        current[part].fileId = file.id;
      }
      current = current[part].children;
    });
  }
  return root;
}

interface NodeProps {
  node: TreeNode;
  depth: number;
  selectedId: number | null;
  onSelect: (fileId: number) => void;
}

function TreeNodeItem({ node, depth, selectedId, onSelect }: NodeProps) {
  const [open, setOpen] = useState(true);
  const isFile = node.fileId !== undefined;
  const isSelected = node.fileId === selectedId;
  const hasChildren = Object.keys(node.children).length > 0;

  if (isFile) {
    const ext = node.name.split('.').pop() ?? '';
    const isCode = ['ts', 'tsx', 'js', 'jsx', 'py', 'css', 'json', 'md'].includes(ext);
    return (
      <button
        onClick={() => onSelect(node.fileId!)}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        className={`flex items-center gap-1.5 w-full text-left py-0.5 pr-2 text-xs rounded transition-colors ${
          isSelected
            ? 'bg-blue-600 text-white'
            : 'hover:bg-[var(--hover)] text-[var(--text-secondary)]'
        }`}
      >
        {isCode ? <FileCode size={12} /> : <File size={12} />}
        <span className="truncate">{node.name}</span>
      </button>
    );
  }

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        className="flex items-center gap-1.5 w-full text-left py-0.5 pr-2 text-xs hover:bg-[var(--hover)] rounded transition-colors"
      >
        {open ? <FolderOpen size={12} /> : <Folder size={12} />}
        <span className="font-medium">{node.name}</span>
      </button>
      {open && hasChildren && (
        <div>
          {Object.values(node.children).map((child) => (
            <TreeNodeItem
              key={child.path}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface FileTreeProps {
  files: StudioFileNode[];
  selectedId: number | null;
  onSelect: (fileId: number) => void;
}

export function FileTree({ files, selectedId, onSelect }: FileTreeProps) {
  const tree = buildTree(files);

  if (files.length === 0) {
    return (
      <div className="p-4 text-xs text-[var(--text-secondary)] opacity-60">
        Файлов пока нет
      </div>
    );
  }

  return (
    <div className="overflow-auto p-1">
      {Object.values(tree).map((node) => (
        <TreeNodeItem
          key={node.path}
          node={node}
          depth={0}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
