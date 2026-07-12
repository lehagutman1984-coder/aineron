'use client';

import { useState } from 'react';
import { Folder, FolderOpen, File, FileCode, FilePlus, Trash2 } from 'lucide-react';
import type { StudioFileNode } from '@/lib/api/studio';
import { tree, btn } from './styles';

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
  onDelete?: (fileId: number) => void;
}

function TreeNodeItem({ node, depth, selectedId, onSelect, onDelete }: NodeProps) {
  const [open, setOpen] = useState(true);
  const [hovered, setHovered] = useState(false);
  const isFile = node.fileId !== undefined;
  const isSelected = node.fileId === selectedId;
  const hasChildren = Object.keys(node.children).length > 0;

  if (isFile) {
    const ext = node.name.split('.').pop() ?? '';
    const isCode = ['ts', 'tsx', 'js', 'jsx', 'py', 'css', 'json', 'md'].includes(ext);
    return (
      <div
        className="group relative"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <button
          onClick={() => onSelect(node.fileId!)}
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
          className={`flex items-center gap-1.5 w-full text-start py-0.5 pe-8 text-xs rounded transition-colors ${
            isSelected
              ? 'bg-blue-600 text-white'
              : 'hover:bg-[var(--hover)] text-[var(--text-secondary)]'
          }`}
        >
          {isCode ? <FileCode size={12} /> : <File size={12} />}
          <span className="truncate">{node.name}</span>
        </button>
        {onDelete && hovered && node.fileId !== undefined && (
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(node.fileId!); }}
            className={tree.deleteBtn}
            title="Удалить файл"
          >
            <Trash2 size={11} />
          </button>
        )}
      </div>
    );
  }

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        className={tree.folderBtn}
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
              onDelete={onDelete}
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
  onCreate?: () => void;
  onDelete?: (fileId: number) => void;
}

export function FileTree({ files, selectedId, onSelect, onCreate, onDelete }: FileTreeProps) {
  const fileTree = buildTree(files);

  return (
    <div className={tree.root}>
      {onCreate && (
        <div className={tree.header}>
          <span className="text-xs text-[var(--text-secondary)]">Файлы</span>
          <button
            onClick={onCreate}
            title="Новый файл"
            className={btn.icon}
          >
            <FilePlus size={14} />
          </button>
        </div>
      )}
      <div className={tree.scrollArea}>
        {files.length === 0 ? (
          <div className={tree.emptyState}>
            Файлов пока нет
          </div>
        ) : (
          Object.values(fileTree).map((node) => (
            <TreeNodeItem
              key={node.path}
              node={node}
              depth={0}
              selectedId={selectedId}
              onSelect={onSelect}
              onDelete={onDelete}
            />
          ))
        )}
      </div>
    </div>
  );
}
