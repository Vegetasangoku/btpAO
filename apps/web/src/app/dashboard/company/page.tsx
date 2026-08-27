'use client';

import React, { useState, useEffect } from 'react';
import {
  Building2,
  Users,
  Globe,
  Upload,
  Trash2,
  Plus,
  Mail,
  ExternalLink,
  Loader2,
  CheckCircle2,
  Copy,
  MessageSquare,
} from 'lucide-react';
import { api } from '@/lib/api';
import { CompanyAsset, TeamMember, TeamInvitation, TeamRole } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';
import { DCEChatSidebar } from '@/components/chat/dce-chat-sidebar';

export default function CompanyUnifiedPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<'knowledge' | 'team' | 'web'>('knowledge');
  const [chatOpen, setChatOpen] = useState(false);

  // --- TAB 1: KNOWLEDGE / SAVOIR-FAIRE ---
  const [assets, setAssets] = useState<CompanyAsset[]>([]);
  const [loadingAssets, setLoadingAssets] = useState(false);
  const [uploadCategory, setUploadCategory] = useState('fiche_technique');
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isUploadingAsset, setIsUploadingAsset] = useState(false);
  const [assetSuccessMsg, setAssetSuccessMsg] = useState<string | null>(null);

  // --- TAB 2: TEAM & RBAC ---
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [invitations, setInvitations] = useState<TeamInvitation[]>([]);
  const [loadingTeam, setLoadingTeam] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<TeamRole>('conducteur_travaux');
  const [isSubmittingInvite, setIsSubmittingInvite] = useState(false);
  const [inviteSuccessMsg, setInviteSuccessMsg] = useState<string | null>(null);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  // --- TAB 3: WEB REFERENCES ---
  const [referenceUrls, setReferenceUrls] = useState<Array<{ id: string; url: string; label?: string; added_at: string; status: string }>>([]);
  const [loadingUrls, setLoadingUrls] = useState(false);
  const [newUrl, setNewUrl] = useState('');
  const [newUrlLabel, setNewUrlLabel] = useState('');
  const [isAddingUrl, setIsAddingUrl] = useState(false);

  useEffect(() => {
    loadAssets();
    loadTeam();
    loadUrls();
  }, []);

  async function loadAssets() {
    setLoadingAssets(true);
    try {
      const data = await api.getAssets().catch(() => []);
      setAssets(data || []);
    } catch (err) {
      console.warn('Erreur chargement assets:', err);
    } finally {
      setLoadingAssets(false);
    }
  }

  async function loadTeam() {
    setLoadingTeam(true);
    try {
      const members = await api.getTeamMembers().catch(() => []);
      const invites = await api.getTeamInvitations().catch(() => []);
      setTeam(members || []);
      setInvitations(invites || []);
    } catch (err) {
      console.warn('Erreur chargement équipe:', err);
    } finally {
      setLoadingTeam(false);
    }
  }

  async function loadUrls() {
    setLoadingUrls(true);
    try {
      const data = await api.getReferenceUrls().catch(() => []);
      setReferenceUrls(data || []);
    } catch (err) {
      console.warn('Erreur chargement URLs:', err);
    } finally {
      setLoadingUrls(false);
    }
  }

  // Handle Asset Upload
  async function handleAssetUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!uploadFile) return;
    setIsUploadingAsset(true);
    setAssetSuccessMsg(null);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('title', uploadTitle || uploadFile.name);
      formData.append('category', uploadCategory);
      await api.uploadKnowledgeDocument(formData);
      setAssetSuccessMsg('Document ajouté au savoir-faire de l’entreprise !');
      setUploadTitle('');
      setUploadFile(null);
      await loadAssets();
    } catch (err: any) {
      alert('Erreur upload document: ' + err.message);
    } finally {
      setIsUploadingAsset(false);
    }
  }

  async function handleDeleteAsset(id: string) {
    if (!confirm('Supprimer ce document du savoir-faire ?')) return;
    try {
      await api.deleteKnowledgeAsset(id);
      setAssets(prev => prev.filter(a => a.id !== id));
    } catch (err: any) {
      alert('Erreur suppression: ' + err.message);
    }
  }

  // Handle Team Actions
  async function handleSendInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail) return;
    setIsSubmittingInvite(true);
    try {
      await api.inviteTeamMember({ email: inviteEmail, role: inviteRole });
      setInviteSuccessMsg(`Invitation envoyée à ${inviteEmail} avec le rôle ${inviteRole} !`);
      setInviteEmail('');
      setShowInviteModal(false);
      await loadTeam();
    } catch (err: any) {
      alert("Erreur lors de l'invitation: " + err.message);
    } finally {
      setIsSubmittingInvite(false);
    }
  }

  async function handleDeleteMember(userId: string) {
    if (!confirm('Retirer ce collaborateur de l’entreprise ?')) return;
    try {
      await api.deleteTeamMember(userId);
      setTeam(prev => prev.filter(m => m.id !== userId));
    } catch (err: any) {
      alert('Erreur: ' + err.message);
    }
  }

  async function handleUpdateRole(userId: string, role: string) {
    try {
      await api.updateTeamMemberRole(userId, role);
      setTeam(prev => prev.map(m => m.id === userId ? { ...m, role: role as any } : m));
    } catch (err: any) {
      alert('Erreur modification rôle: ' + err.message);
    }
  }

  // Handle URL Add
  async function handleAddUrl(e: React.FormEvent) {
    e.preventDefault();
    if (!newUrl) return;
    setIsAddingUrl(true);
    try {
      await api.addReferenceUrl({ url: newUrl, label: newUrlLabel });
      setNewUrl('');
      setNewUrlLabel('');
      await loadUrls();
    } catch (err: any) {
      alert('Erreur ajout URL: ' + err.message);
    } finally {
      setIsAddingUrl(false);
    }
  }

  async function handleDeleteUrl(id: string) {
    if (!confirm('Supprimer ce site de référence ?')) return;
    try {
      await api.deleteReferenceUrl(id);
      setReferenceUrls(prev => prev.filter(u => u.id !== id));
    } catch (err: any) {
      alert('Erreur: ' + err.message);
    }
  }

  function getCategoryLabel(category: string) {
    switch (category) {
      case 'fiche_technique':
        return t('company.cat_technical_sheet');
      case 'memoire_reference':
        return t('company.cat_past_proposal');
      case 'certification':
        return t('company.cat_certification');
      case 'qse_securite':
        return t('company.cat_qse_safety');
      case 'moyens_materiels':
        return t('company.cat_equipment_fleet');
      default:
        return category.replace('_', ' ');
    }
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-20">
      {/* Top Banner */}
      <div className="p-6 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] shadow-subtle space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                {t('company.badge')}
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-white font-heading">
              {t('company.title')}
            </h1>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              {t('company.desc')}
            </p>
          </div>

          <button
            onClick={() => setChatOpen(true)}
            className="shrink-0 flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-bold font-heading border bg-amber-500/15 border-amber-500 text-slate-900 dark:text-white hover:bg-amber-500/25 transition-all shadow-subtle"
          >
            <MessageSquare className="w-4 h-4 text-amber-500" />
            <span>Assistant Q&A</span>
          </button>
        </div>

        {/* 3 Sub-Tabs Header */}
        <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-200 dark:border-[#1E2638]">
          {[
            { id: 'knowledge', label: t('company.tab_knowledge'), icon: Building2, count: assets.length },
            { id: 'team', label: t('company.tab_team'), icon: Users, count: team.length },
            { id: 'web', label: t('company.tab_web'), icon: Globe, count: referenceUrls.length },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold font-heading border transition-all ${
                  isActive
                    ? 'bg-amber-500/15 border-amber-500 text-slate-900 dark:text-white shadow-subtle'
                    : 'bg-transparent border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-[#1E2638]'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-amber-500' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                  {tab.count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* --- SUB-TAB 1: SAVOIR-FAIRE & DOCUMENTS --- */}
      {activeTab === 'knowledge' && (
        <div className="space-y-6">
          {/* Upload Form Card */}
          <div className="p-6 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-4 shadow-subtle">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
              <Upload className="w-4 h-4 text-amber-500" />
              <span>{t('company.add_doc_title')}</span>
            </h2>

            <form onSubmit={handleAssetUpload} className="grid grid-cols-1 sm:grid-cols-4 gap-3">
              <div className="space-y-1 sm:col-span-2">
                <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">{t('company.label_title_ref')}</label>
                <input
                  type="text"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  placeholder={t('company.placeholder_title')}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">{t('company.label_category')}</label>
                <select
                  value={uploadCategory}
                  onChange={(e) => setUploadCategory(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
                >
                  <option value="fiche_technique">{t('company.cat_technical_sheet')}</option>
                  <option value="memoire_reference">{t('company.cat_past_proposal')}</option>
                  <option value="certification">{t('company.cat_certification')}</option>
                  <option value="qse_securite">{t('company.cat_qse_safety')}</option>
                  <option value="moyens_materiels">{t('company.cat_equipment_fleet')}</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">{t('company.label_file')}</label>
                <input
                  type="file"
                  required
                  accept=".pdf,.docx,.doc"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="w-full text-[11px] text-slate-500 file:mr-2 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-amber-600 file:text-white file:text-xs file:font-semibold"
                />
                {uploadFile && (
                  <p className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold truncate">
                    ✓ {uploadFile.name} sélectionné
                  </p>
                )}
              </div>

              <div className="sm:col-span-4 flex justify-end">
                <button
                  type="submit"
                  disabled={isUploadingAsset || !uploadFile}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold font-heading shadow-subtle transition-all disabled:opacity-50"
                >
                  {isUploadingAsset ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                  <span>{t('common.save')}</span>
                </button>
              </div>
            </form>

            {assetSuccessMsg && (
              <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-300 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs font-semibold flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                <span>{assetSuccessMsg}</span>
              </div>
            )}
          </div>

          {/* Asset List */}
          <div className="p-6 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-4 shadow-subtle">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white font-heading">
              {t('company.indexed_docs')} ({assets.length})
            </h2>

            {loadingAssets ? (
              <div className="p-8 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-amber-500" />
                <span>{t('dash.loading')}</span>
              </div>
            ) : assets.length === 0 ? (
              <div className="p-8 text-center space-y-2">
                <Building2 className="w-8 h-8 text-slate-400 mx-auto" />
                <p className="text-xs font-bold text-slate-700 dark:text-slate-300">{t('company.empty_knowledge_title')}</p>
                <p className="text-[11px] text-slate-500">{t('company.empty_knowledge_desc')}</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-200 dark:divide-[#1E2638]">
                {assets.map((asset) => (
                  <div key={asset.id} className="py-3 flex items-center justify-between gap-4">
                    <div className="space-y-0.5 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-amber-600 dark:text-amber-400">
                          {getCategoryLabel(asset.category)}
                        </span>
                        <p className="text-xs font-bold text-slate-900 dark:text-white truncate">
                          {asset.title}
                        </p>
                      </div>
                      <p className="text-[10px] text-slate-500">
                        {asset.description || 'Document indexé pour les citations et preuves'}
                      </p>
                    </div>

                    <button
                      onClick={() => handleDeleteAsset(asset.id)}
                      className="text-slate-400 hover:text-rose-500 p-1.5 rounded transition-colors"
                      title={t('common.delete')}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* --- SUB-TAB 2: ÉQUIPE & CONDUCTEURS --- */}
      {activeTab === 'team' && (
        <div className="space-y-6">
          <div className="p-6 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-4 shadow-subtle">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
                  <Users className="w-4 h-4 text-amber-500" />
                  <span>{t('company.team_title')}</span>
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {t('company.team_desc')}
                </p>
              </div>

              <button
                onClick={() => setShowInviteModal(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold font-heading shadow-subtle transition-all"
              >
                <Mail className="w-3.5 h-3.5" />
                <span>{t('company.invite_btn')}</span>
              </button>
            </div>

            {/* Members List */}
            {loadingTeam ? (
              <div className="p-8 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-amber-500" />
                <span>{t('dash.loading')}</span>
              </div>
            ) : (
              <div className="divide-y divide-slate-200 dark:divide-[#1E2638]">
                {team.map((member) => (
                  <div key={member.id} className="py-3 flex flex-wrap items-center justify-between gap-4">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 font-bold text-xs flex items-center justify-center">
                        {(member.full_name || member.email || 'U').substring(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <p className="text-xs font-bold text-slate-900 dark:text-white">
                          {member.full_name || member.email}
                        </p>
                        <p className="text-[10px] text-slate-500 font-mono">{member.email}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <select
                        value={member.role}
                        onChange={(e) => handleUpdateRole(member.id, e.target.value)}
                        className="px-2.5 py-1 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-[11px] text-slate-800 dark:text-slate-200 font-semibold"
                      >
                        <option value="owner">{t('company.role_owner')}</option>
                        <option value="conducteur_travaux">{t('company.role_site_manager')}</option>
                        <option value="chiffreur">{t('company.role_estimator')}</option>
                        <option value="member">{t('company.role_member')}</option>
                        <option value="read_only">{t('company.role_read_only')}</option>
                      </select>

                      <button
                        onClick={() => handleDeleteMember(member.id)}
                        className="text-slate-400 hover:text-rose-500 p-1.5 rounded transition-colors"
                        title={t('common.delete')}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Pending Invitations */}
          {invitations.length > 0 && (
            <div className="p-6 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-3 shadow-subtle">
              <h3 className="text-xs font-bold text-slate-900 dark:text-white font-heading">
                {t('company.pending_invites')} ({invitations.length})
              </h3>
              <div className="space-y-2">
                {invitations.map((inv) => (
                  <div key={inv.id} className="p-3 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-200 dark:border-[#1E2638] flex items-center justify-between text-xs">
                    <div>
                      <p className="font-bold text-slate-800 dark:text-slate-200">{inv.email}</p>
                      <p className="text-[10px] text-slate-500">{t('company.label_assigned_role')} : {inv.role}</p>
                    </div>
                    <button
                      onClick={() => {
                        const tokenVal = inv.invitation_token || inv.token || '';
                        const link = `${window.location.origin}/register?invitation=${tokenVal}`;
                        navigator.clipboard.writeText(link);
                        setCopiedToken(tokenVal);
                        setTimeout(() => setCopiedToken(null), 2000);
                      }}
                      className="flex items-center gap-1 text-[11px] text-amber-600 dark:text-amber-400 hover:underline font-semibold"
                    >
                      <Copy className="w-3.5 h-3.5" />
                      <span>{copiedToken === (inv.invitation_token || inv.token) ? t('company.copied') : t('company.copy_link')}</span>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Invite Modal */}
          {showInviteModal && (
            <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50 animate-in fade-in">
              <div className="p-6 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] max-w-md w-full space-y-4 shadow-floating">
                <h3 className="text-sm font-bold text-slate-900 dark:text-white font-heading">{t('company.modal_invite_title')}</h3>
                <form onSubmit={handleSendInvite} className="space-y-3">
                  <div className="space-y-1">
                    <label className="text-xs text-slate-600 dark:text-slate-400">{t('company.label_email')}</label>
                    <input
                      type="email"
                      required
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      placeholder="collaborateur@entreprise.fr"
                      className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs text-slate-600 dark:text-slate-400">{t('company.label_assigned_role')}</label>
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value as any)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
                    >
                      <option value="conducteur_travaux">{t('company.role_site_manager')}</option>
                      <option value="chiffreur">{t('company.role_estimator')}</option>
                      <option value="owner">{t('company.role_owner')}</option>
                      <option value="member">{t('company.role_member')}</option>
                      <option value="read_only">{t('company.role_read_only')}</option>
                    </select>
                  </div>

                  <div className="flex justify-end gap-2 pt-3">
                    <button
                      type="button"
                      onClick={() => setShowInviteModal(false)}
                      className="px-4 py-2 rounded-lg bg-slate-100 dark:bg-[#1E2638] text-slate-700 dark:text-slate-300 text-xs font-semibold"
                    >
                      {t('common.cancel')}
                    </button>
                    <button
                      type="submit"
                      disabled={isSubmittingInvite}
                      className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold font-heading"
                    >
                      {isSubmittingInvite ? 'Envoi...' : t('company.btn_send_invite')}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}

      {/* --- SUB-TAB 3: SITES & RÉFÉRENCES WEB --- */}
      {activeTab === 'web' && (
        <div className="space-y-6">
          <div className="p-6 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-4 shadow-subtle">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
              <Globe className="w-4 h-4 text-amber-500" />
              <span>{t('company.web_title')}</span>
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              {t('company.web_desc')}
            </p>

            <form onSubmit={handleAddUrl} className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <input
                type="url"
                required
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                placeholder={t('company.placeholder_url')}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500 sm:col-span-2"
              />
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newUrlLabel}
                  onChange={(e) => setNewUrlLabel(e.target.value)}
                  placeholder={t('company.placeholder_url_label')}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
                />
                <button
                  type="submit"
                  disabled={isAddingUrl}
                  className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold font-heading shrink-0"
                >
                  {isAddingUrl ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : t('company.btn_add_url')}
                </button>
              </div>
            </form>

            {/* URL List */}
            {loadingUrls ? (
              <div className="p-8 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-amber-500" />
                <span>{t('dash.loading')}</span>
              </div>
            ) : referenceUrls.length === 0 ? (
              <div className="p-8 text-center space-y-2">
                <Globe className="w-8 h-8 text-slate-400 mx-auto" />
                <p className="text-xs font-bold text-slate-700 dark:text-slate-300">{t('company.empty_web_title')}</p>
                <p className="text-[11px] text-slate-500">{t('company.empty_web_desc')}</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-200 dark:divide-[#1E2638]">
                {referenceUrls.map((u) => (
                  <div key={u.id} className="py-3 flex items-center justify-between gap-4">
                    <div className="space-y-0.5 min-w-0">
                      <p className="text-xs font-bold text-slate-900 dark:text-white truncate">
                        {u.label || u.url}
                      </p>
                      <a
                        href={u.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[11px] text-amber-600 dark:text-amber-400 hover:underline flex items-center gap-1 font-mono truncate"
                      >
                        <span>{u.url}</span>
                        <ExternalLink className="w-3 h-3 shrink-0" />
                      </a>
                    </div>

                    <button
                      onClick={() => handleDeleteUrl(u.id)}
                      className="text-slate-400 hover:text-rose-500 p-1.5 rounded transition-colors"
                      title={t('common.delete')}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <DCEChatSidebar
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
        mode="company"
      />
    </div>
  );
}
