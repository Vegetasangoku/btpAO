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
  FileText,
  FolderKanban,
  Search,
  Check,
  Shield,
  FileCode,
  HardHat,
  Filter,
  Eye,
  Download,
  RefreshCw,
  Cloud,
  Brain,
  Pencil,
  Save,
  XCircle,
  User,
} from 'lucide-react';
import { api } from '@/lib/api';
import { CompanyAsset, TeamMember, TeamInvitation, TeamRole, SharePointStatus, TenantLearning } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';
import { DCEChatSidebar } from '@/components/chat/dce-chat-sidebar';

export default function CompanyUnifiedPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<'knowledge' | 'team' | 'web' | 'learnings'>('knowledge');
  const [chatOpen, setChatOpen] = useState(false);

  // --- TAB 1: KNOWLEDGE / SAVOIR-FAIRE ---
  const [assets, setAssets] = useState<CompanyAsset[]>([]);
  const [loadingAssets, setLoadingAssets] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState('all');
  const [uploadCategory, setUploadCategory] = useState('fiche_technique');
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isUploadingAsset, setIsUploadingAsset] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
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
  const [referenceUrls, setReferenceUrls] = useState<Array<{ id: string; url: string; label?: string; added_at: string; status: string; last_fetch_error?: string | null }>>([]);
  const [loadingUrls, setLoadingUrls] = useState(false);
  const [newUrl, setNewUrl] = useState('');
  const [newUrlLabel, setNewUrlLabel] = useState('');
  const [isAddingUrl, setIsAddingUrl] = useState(false);
  const [refreshingUrlId, setRefreshingUrlId] = useState<string | null>(null);

  // --- SHAREPOINT : autre source pour la base de connaissance (14/09) ---
  const [spStatus, setSpStatus] = useState<SharePointStatus | null>(null);
  const [loadingSp, setLoadingSp] = useState(false);
  const [showSpModal, setShowSpModal] = useState(false);
  const [spForm, setSpForm] = useState({ ms_tenant_id: '', client_id: '', client_secret: '', site_url: '', selected_folder_path: '/' });
  const [connectingSp, setConnectingSp] = useState(false);
  const [syncingSp, setSyncingSp] = useState(false);
  const [spActionError, setSpActionError] = useState<string | null>(null);

  // --- TAB 4: CE QUE L'APPLICATION A APPRIS DE L'ENTREPRISE (14/09) ---
  const [learnings, setLearnings] = useState<TenantLearning[]>([]);
  const [loadingLearnings, setLoadingLearnings] = useState(false);
  const [editingLearningId, setEditingLearningId] = useState<string | null>(null);
  const [editLearningForm, setEditLearningForm] = useState({ title: '', learning_insight: '', actionable_directive: '' });
  const [savingLearningId, setSavingLearningId] = useState<string | null>(null);
  const [learningCategoryFilter, setLearningCategoryFilter] = useState('all');
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [showNewLearningForm, setShowNewLearningForm] = useState(false);
  const [newLearningForm, setNewLearningForm] = useState({ title: '', actionable_directive: '', category: 'general', personal: false });
  const [creatingLearning, setCreatingLearning] = useState(false);

  useEffect(() => {
    loadAssets();
    loadTeam();
    loadUrls();
    loadSpStatus();
    loadLearnings();
    loadCurrentUser();
  }, []);

  async function loadCurrentUser() {
    try {
      const profile = await api.getProfile();
      setCurrentUserId(profile?.id || null);
    } catch (err) {
      console.warn('Erreur chargement profil utilisateur:', err);
    }
  }

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

  async function loadSpStatus() {
    setLoadingSp(true);
    try {
      const data = await api.getSharePointStatus().catch(() => null);
      setSpStatus(data);
    } catch (err) {
      console.warn('Erreur chargement statut SharePoint:', err);
    } finally {
      setLoadingSp(false);
    }
  }

  async function loadLearnings() {
    setLoadingLearnings(true);
    try {
      const data = await api.getTenantLearnings().catch(() => []);
      setLearnings(data || []);
    } catch (err) {
      console.warn('Erreur chargement apprentissages:', err);
    } finally {
      setLoadingLearnings(false);
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
      setAssetSuccessMsg('Document ajouté avec succès au savoir-faire !');
      setUploadTitle('');
      setUploadFile(null);
      setShowUploadModal(false);
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
      setAssets((prev) => prev.filter((a) => a.id !== id));
    } catch (err: any) {
      alert('Erreur suppression: ' + err.message);
    }
  }

  const [openingAssetId, setOpeningAssetId] = useState<string | null>(null);

  async function handleViewAsset(asset: CompanyAsset) {
    setOpeningAssetId(asset.id);
    try {
      const url = await api.getKnowledgeAssetBlobUrl(asset.id, true);
      window.open(url, '_blank');
    } catch (err: any) {
      alert("Impossible de prévisualiser ce document : " + (err.message || 'Erreur inconnue'));
    } finally {
      setOpeningAssetId(null);
    }
  }

  async function handleDownloadAsset(asset: CompanyAsset) {
    setOpeningAssetId(asset.id);
    try {
      const url = await api.getKnowledgeAssetBlobUrl(asset.id, false);
      const a = document.createElement('a');
      a.href = url;
      a.download = (asset.metadata_json as any)?.file_name || asset.title || 'document';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err: any) {
      alert("Erreur lors du téléchargement : " + (err.message || 'Erreur inconnue'));
    } finally {
      setOpeningAssetId(null);
    }
  }

  // Handle Team Actions
  async function handleSendInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail) return;
    setIsSubmittingInvite(true);
    try {
      await api.inviteTeamMember({ email: inviteEmail, role: inviteRole });
      setInviteSuccessMsg(`Invitation envoyée à ${inviteEmail} !`);
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
    if (!confirm("Retirer ce collaborateur de l'entreprise ?")) return;
    try {
      await api.deleteTeamMember(userId);
      setTeam((prev) => prev.filter((m) => m.id !== userId));
    } catch (err: any) {
      alert('Erreur: ' + err.message);
    }
  }

  async function handleUpdateRole(userId: string, role: string) {
    try {
      await api.updateTeamMemberRole(userId, role);
      setTeam((prev) => prev.map((m) => (m.id === userId ? { ...m, role: role as any } : m)));
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
      setReferenceUrls((prev) => prev.filter((u) => u.id !== id));
    } catch (err: any) {
      alert('Erreur: ' + err.message);
    }
  }

  async function handleRefreshUrl(id: string) {
    setRefreshingUrlId(id);
    try {
      await api.refreshReferenceUrl(id);
      await loadUrls();
    } catch (err: any) {
      alert('Erreur actualisation: ' + err.message);
    } finally {
      setRefreshingUrlId(null);
    }
  }

  // Handle SharePoint
  async function handleConnectSharePoint(e: React.FormEvent) {
    e.preventDefault();
    setConnectingSp(true);
    setSpActionError(null);
    try {
      const status = await api.connectSharePoint(spForm);
      setSpStatus(status);
      setShowSpModal(false);
      setSpForm({ ms_tenant_id: '', client_id: '', client_secret: '', site_url: '', selected_folder_path: '/' });
    } catch (err: any) {
      setSpActionError(err.message || 'Erreur de connexion à SharePoint.');
    } finally {
      setConnectingSp(false);
    }
  }

  async function handleSyncSharePoint() {
    setSyncingSp(true);
    try {
      const status = await api.syncSharePoint();
      setSpStatus(status);
    } catch (err: any) {
      alert('Erreur synchronisation SharePoint: ' + err.message);
    } finally {
      setSyncingSp(false);
    }
  }

  async function handleDisconnectSharePoint() {
    if (!confirm('Déconnecter SharePoint ? Les fichiers déjà indexés restent dans votre base de connaissance.')) return;
    try {
      await api.disconnectSharePoint();
      await loadSpStatus();
    } catch (err: any) {
      alert('Erreur déconnexion: ' + err.message);
    }
  }

  // Handle Learnings
  function startEditLearning(l: TenantLearning) {
    setEditingLearningId(l.id);
    setEditLearningForm({ title: l.title, learning_insight: l.learning_insight, actionable_directive: l.actionable_directive });
  }

  async function handleSaveLearning(id: string) {
    setSavingLearningId(id);
    try {
      const updated = await api.updateTenantLearning(id, editLearningForm);
      setLearnings((prev) => prev.map((l) => (l.id === id ? updated : l)));
      setEditingLearningId(null);
    } catch (err: any) {
      alert('Erreur enregistrement: ' + err.message);
    } finally {
      setSavingLearningId(null);
    }
  }

  async function handleToggleLearningActive(l: TenantLearning) {
    try {
      const updated = await api.updateTenantLearning(l.id, { is_active: !l.is_active });
      setLearnings((prev) => prev.map((x) => (x.id === l.id ? updated : x)));
    } catch (err: any) {
      alert('Erreur: ' + err.message);
    }
  }

  async function handleDeleteLearning(id: string) {
    if (!confirm("Supprimer cet apprentissage ? L'application cessera d'en tenir compte dans les prochains dossiers.")) return;
    try {
      await api.deleteTenantLearning(id);
      setLearnings((prev) => prev.filter((l) => l.id !== id));
    } catch (err: any) {
      alert('Erreur suppression: ' + err.message);
    }
  }

  // 15/09 : enseignement ajouté explicitement (pas issu d'un retour gagné/perdu) -- l'aspect
  // "je change explicitement des données à retenir" demandé, en complément de l'aspect
  // automatique déjà en place (débrief marché + détection d'écart). personal=true le réserve à
  // l'auteur ; personal=false (défaut) le rend visible par toute l'équipe.
  async function handleCreateLearning() {
    if (!newLearningForm.title.trim() || !newLearningForm.actionable_directive.trim()) {
      alert('Merci de renseigner au moins un titre et la consigne à appliquer.');
      return;
    }
    setCreatingLearning(true);
    try {
      const directive = newLearningForm.actionable_directive.trim();
      const created = await api.createLearning({
        title: newLearningForm.title.trim(),
        actionable_directive: directive,
        // Pas de source distincte pour un ajout manuel : la consigne saisie EST le contenu appris.
        learned_content: directive,
        category: newLearningForm.category,
        source_outcome: 'manual',
        personal: newLearningForm.personal,
      });
      setLearnings((prev) => [created, ...prev]);
      setNewLearningForm({ title: '', actionable_directive: '', category: 'general', personal: false });
      setShowNewLearningForm(false);
    } catch (err: any) {
      alert("Erreur lors de l'ajout: " + err.message);
    } finally {
      setCreatingLearning(false);
    }
  }

  function getLearningCategoryLabel(category: string) {
    switch (category) {
      case 'planning': return 'Planning';
      case 'methodology': return 'Méthodologie';
      case 'qse': return 'QSE / Environnement';
      case 'safety': return 'Sécurité';
      case 'pricing': return 'Tarification';
      default: return 'Général';
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
      case 'autre':
        return t('company.cat_other');
      default:
        return category.replace('_', ' ');
    }
  }

  // Filtered Assets
  const filteredAssets = assets.filter((asset) => {
    const matchesSearch = asset.title.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCat = selectedCategoryFilter === 'all' || asset.category === selectedCategoryFilter;
    return matchesSearch && matchesCat;
  });

  const countFiches = assets.filter((a) => a.category === 'fiche_technique').length;
  const countMemoires = assets.filter((a) => a.category === 'memoire_reference').length;
  const countCerts = assets.filter((a) => a.category === 'certification' || a.category === 'qse_securite').length;
  const filteredLearnings = learnings.filter((l) => learningCategoryFilter === 'all' || l.category === learningCategoryFilter);

  return (
    <div className="page-container max-w-7xl mx-auto space-y-6">
      
      {/* ─── TAILGRIDS FILE MANAGER TOP STORAGE & ANALYTICS CARDS ─── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        
        {/* Card 1: All Documents */}
        <div className="bg-card border border-line rounded-2xl p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="w-10 h-10 rounded-xl bg-hl text-hl-contrast flex items-center justify-center font-bold shadow-xs">
              <FolderKanban className="w-5 h-5" />
            </div>
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Fichiers RAG</span>
          </div>
          <div>
            <span className="text-2xl font-black font-heading text-foreground">{assets.length}</span>
            <p className="text-[11px] text-muted-foreground mt-0.5">Documents d'entreprise indexés</p>
          </div>
          <div className="w-full bg-sunken rounded-full h-1.5 overflow-hidden">
            <div className="bg-hl h-1.5 rounded-full" style={{ width: `${Math.min(100, (assets.length / 20) * 100)}%` }} />
          </div>
        </div>

        {/* Card 2: Fiches Techniques */}
        <div className="bg-card border border-line rounded-2xl p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="w-10 h-10 rounded-xl bg-hl/10 text-hl flex items-center justify-center font-bold">
              <FileText className="w-5 h-5" />
            </div>
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Technique</span>
          </div>
          <div>
            <span className="text-2xl font-black font-heading text-foreground">{countFiches}</span>
            <p className="text-[11px] text-muted-foreground mt-0.5">Fiches matériaux & procédés</p>
          </div>
          <div className="w-full bg-sunken rounded-full h-1.5 overflow-hidden">
            <div className="bg-hl h-1.5 rounded-full" style={{ width: `${Math.min(100, (countFiches / 10) * 100)}%` }} />
          </div>
        </div>

        {/* Card 3: Mémoires & Références */}
        <div className="bg-card border border-line rounded-2xl p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="w-10 h-10 rounded-xl bg-positive/10 text-positive flex items-center justify-center font-bold">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Références</span>
          </div>
          <div>
            <span className="text-2xl font-black font-heading text-foreground">{countMemoires + countCerts}</span>
            <p className="text-[11px] text-muted-foreground mt-0.5">Mémoires & Certifications</p>
          </div>
          <div className="w-full bg-sunken rounded-full h-1.5 overflow-hidden">
            <div className="bg-positive h-1.5 rounded-full" style={{ width: `${Math.min(100, ((countMemoires + countCerts) / 10) * 100)}%` }} />
          </div>
        </div>

        {/* Card 4: Équipe & Collaborateurs */}
        <div className="bg-card border border-line rounded-2xl p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="w-10 h-10 rounded-xl bg-hl/10 text-hl flex items-center justify-center font-bold">
              <Users className="w-5 h-5" />
            </div>
            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Collaborateurs</span>
          </div>
          <div>
            <span className="text-2xl font-black font-heading text-foreground">{team.length}</span>
            <p className="text-[11px] text-muted-foreground mt-0.5">Membres avec accès RBAC</p>
          </div>
          <div className="w-full bg-sunken rounded-full h-1.5 overflow-hidden">
            <div className="bg-hl h-1.5 rounded-full" style={{ width: `${Math.min(100, (team.length / 5) * 100)}%` }} />
          </div>
        </div>

      </div>

      {/* ─── TAILGRIDS MAIN FILE MANAGER CANVAS ─── */}
      <div className="bg-card border border-line rounded-2xl shadow-xs overflow-hidden">
        
        {/* Header Bar with Tabs & Main Actions */}
        <div className="p-5 border-b border-line flex flex-wrap items-center justify-between gap-4">
          
          {/* Segmented Nav Tabs */}
          <div className="flex items-center bg-sunken rounded-xl p-1 border border-line">
            {[
              { id: 'knowledge' as const, label: t('company.tab_knowledge'), icon: FolderKanban, count: assets.length },
              { id: 'team' as const, label: t('company.tab_team'), icon: Users, count: team.length },
              { id: 'web' as const, label: t('company.tab_web'), icon: Globe, count: referenceUrls.length },
              { id: 'learnings' as const, label: t('company.tab_learnings'), icon: Brain, count: learnings.length },
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                    isActive
                      ? 'bg-card text-hl shadow-xs'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-hl' : ''}`} />
                  <span>{tab.label}</span>
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                    isActive ? 'bg-hl/15 text-hl' : 'bg-slate-200 dark:bg-raised text-muted-foreground'
                  }`}>
                    {tab.count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => setChatOpen(true)}
              className="btn-secondary !py-2 !px-3 !text-xs cursor-pointer"
            >
              <MessageSquare className="w-3.5 h-3.5 text-hl" />
              <span>Assistant Q&A</span>
            </button>

            {activeTab === 'knowledge' && (
              <button
                onClick={() => setShowUploadModal(true)}
                className="btn-primary !py-2 !px-3.5 !text-xs cursor-pointer"
              >
                <Upload className="w-3.5 h-3.5" />
                <span>+ Importer un document</span>
              </button>
            )}

            {activeTab === 'team' && (
              <button
                onClick={() => setShowInviteModal(true)}
                className="btn-primary !py-2 !px-3.5 !text-xs cursor-pointer"
              >
                <Mail className="w-3.5 h-3.5" />
                <span>+ Inviter un membre</span>
              </button>
            )}
          </div>
        </div>

        {/* ═══ TAB 1: SAVOIR-FAIRE FILE MANAGER ═══ */}
        {activeTab === 'knowledge' && (
          <div className="p-5 space-y-5 animate-fade-in-up">

            {/* SharePoint : autre source pour la base de connaissance (14/09) */}
            <div className="border border-line rounded-2xl p-4 sm:p-5 bg-sunken/40 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${spStatus?.connected ? 'bg-positive/10 text-positive' : 'bg-hl/10 text-hl'}`}>
                    <Cloud className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-foreground">SharePoint</p>
                    <p className="text-[11px] text-muted-foreground truncate">
                      {loadingSp
                        ? 'Vérification…'
                        : spStatus?.connected
                        ? `Connecté — ${spStatus.site_url || ''}`
                        : "Ajoutez les documents de votre SharePoint d'entreprise à la base de connaissance."}
                    </p>
                  </div>
                </div>

                {!loadingSp && (
                  spStatus?.connected ? (
                    <div className="flex items-center gap-2 shrink-0">
                      <button onClick={handleSyncSharePoint} disabled={syncingSp} className="btn-secondary !py-1.5 !px-3 !text-[11px] cursor-pointer">
                        {syncingSp ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                        <span>Synchroniser</span>
                      </button>
                      <button onClick={handleDisconnectSharePoint} className="p-1.5 rounded-lg text-slate-400 hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer" title="Déconnecter">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ) : (
                    <button onClick={() => setShowSpModal(true)} className="btn-primary !py-1.5 !px-3.5 !text-[11px] cursor-pointer shrink-0">
                      <Cloud className="w-3.5 h-3.5" />
                      <span>Connecter SharePoint</span>
                    </button>
                  )
                )}
              </div>

              {spStatus?.connected && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-line text-[11px]">
                  <div>
                    <p className="text-muted-foreground">Dossier suivi</p>
                    <p className="font-mono font-semibold text-foreground truncate">{spStatus.selected_folder_path || '/'}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Fichiers indexés (mois)</p>
                    <p className="font-semibold text-foreground">
                      {spStatus.files_indexed_this_month}{spStatus.files_quota_this_month != null ? ` / ${spStatus.files_quota_this_month}` : ''}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Dernière synchro</p>
                    <p className="font-semibold text-foreground">{spStatus.last_synced_at ? new Date(spStatus.last_synced_at).toLocaleString('fr-FR') : 'Jamais'}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Statut</p>
                    <p className={`font-semibold ${spStatus.status === 'error' ? 'text-danger' : 'text-positive'}`}>{spStatus.status}</p>
                  </div>
                </div>
              )}
              {spStatus?.connected && spStatus.last_error && (
                <p className="text-[11px] text-danger bg-danger/5 border border-danger/20 rounded-lg p-2">{spStatus.last_error}</p>
              )}
            </div>

            {/* Search and Category Filter Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="relative max-w-sm w-full">
                <Search className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Rechercher un fichier ou une référence..."
                  className="input-field pl-10 !py-2 !text-xs"
                />
              </div>

              <div className="flex flex-wrap items-center gap-1.5">
                {[
                  { id: 'all', label: 'Tous les fichiers' },
                  { id: 'fiche_technique', label: 'Fiches Techniques' },
                  { id: 'memoire_reference', label: 'Mémoires Passés' },
                  { id: 'certification', label: 'Certifications' },
                  { id: 'qse_securite', label: 'QSE' },
                ].map((cat) => (
                  <button
                    key={cat.id}
                    onClick={() => setSelectedCategoryFilter(cat.id)}
                    className={`px-3 py-1.5 rounded-xl text-[11px] font-semibold border transition-all cursor-pointer ${
                      selectedCategoryFilter === cat.id
                        ? 'bg-hl text-hl-contrast border-hl shadow-xs'
                        : 'border-line text-muted-foreground hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-raised'
                    }`}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Notification alert */}
            {assetSuccessMsg && (
              <div className="p-3 rounded-xl bg-positive/10 border border-positive/25 text-positive text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-positive shrink-0" />
                <span>{assetSuccessMsg}</span>
              </div>
            )}

            {/* Tableau des documents */}
            <div className="border border-line rounded-xl overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-sunken border-b border-line text-muted-foreground font-semibold uppercase tracking-wider text-[10px]">
                  <tr>
                    <th className="py-3 px-4">Document / Titre</th>
                    <th className="py-3 px-4">Catégorie</th>
                    <th className="py-3 px-4">Date d'indexation</th>
                    <th className="py-3 px-4">Statut RAG</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200/80 dark:divide-line/80">
                  {loadingAssets ? (
                    <tr>
                      <td colSpan={5} className="py-12 text-center text-muted-foreground">
                        <Loader2 className="w-5 h-5 animate-spin text-hl mx-auto mb-2" />
                        <span>Chargement des documents...</span>
                      </td>
                    </tr>
                  ) : filteredAssets.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-12 text-center text-muted-foreground space-y-2">
                        <FolderKanban className="w-8 h-8 text-slate-300 dark:text-zinc-600 mx-auto" />
                        <p className="font-semibold text-foreground">Aucun document trouvé</p>
                        <p className="text-[11px]">Importez votre premier mémoire technique ou fiche produit ci-dessus.</p>
                      </td>
                    </tr>
                  ) : (
                    filteredAssets.map((asset) => (
                      <tr key={asset.id} className="hover:bg-slate-50/70 dark:hover:bg-raised/50 transition-colors">
                        <td className="py-3.5 px-4 font-semibold text-foreground">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-sunken text-foreground border border-line flex items-center justify-center shrink-0">
                              <FileText className="w-4 h-4 text-hl" />
                            </div>
                            <div
                              className="truncate max-w-xs sm:max-w-md cursor-pointer group"
                              onClick={() => handleViewAsset(asset)}
                            >
                              <p className="truncate text-xs font-bold text-foreground group-hover:text-hl transition-colors">
                                {asset.title}
                              </p>
                              <p className="text-[10px] text-muted-foreground truncate font-mono">
                                {(asset.metadata_json as any)?.file_name || asset.description || 'Fichier indexé'}
                              </p>
                            </div>
                          </div>
                        </td>

                        <td className="py-3.5 px-4">
                          <span className="badge-pill text-[10px]">
                            {getCategoryLabel(asset.category)}
                          </span>
                        </td>

                        <td className="py-3.5 px-4 text-muted-foreground font-mono text-[11px]">
                          {asset.created_at ? new Date(asset.created_at).toLocaleDateString('fr-FR') : '—'}
                        </td>

                        <td className="py-3.5 px-4">
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-positive/10 text-positive border border-positive/25 text-[10px] font-bold">
                            <span className="w-1.5 h-1.5 rounded-full bg-positive animate-pulse" />
                            <span>Prêt pour citation</span>
                          </span>
                        </td>

                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => handleViewAsset(asset)}
                              disabled={openingAssetId === asset.id}
                              className="p-1.5 rounded-lg text-slate-500 hover:text-hl hover:bg-hl/10 transition-colors cursor-pointer"
                              title="Visualiser le document"
                            >
                              {openingAssetId === asset.id ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin text-hl" />
                              ) : (
                                <Eye className="w-3.5 h-3.5" />
                              )}
                            </button>
                            <button
                              onClick={() => handleDownloadAsset(asset)}
                              disabled={openingAssetId === asset.id}
                              className="p-1.5 rounded-lg text-slate-500 hover:text-positive hover:bg-positive/10 transition-colors cursor-pointer"
                              title="Télécharger le fichier original"
                            >
                              <Download className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => handleDeleteAsset(asset.id)}
                              className="p-1.5 rounded-lg text-slate-400 hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer"
                              title="Supprimer"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

          </div>
        )}

        {/* ═══ TAB 2: TEAM & RBAC ═══ */}
        {activeTab === 'team' && (
          <div className="p-5 space-y-5 animate-fade-in-up">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-foreground font-heading">Collaborateurs & Permissions</h3>
                <p className="text-xs text-muted-foreground">Gérez les accès aux projets d'appels d'offres et à la base de données de l'entreprise.</p>
              </div>
            </div>

            {/* Team Table */}
            <div className="border border-line rounded-2xl overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs">
                <thead className="bg-sunken border-b border-line text-muted-foreground font-semibold uppercase tracking-wider text-[10px]">
                  <tr>
                    <th className="py-3 px-4">Membre</th>
                    <th className="py-3 px-4">Rôle & Permissions</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {loadingTeam ? (
                    <tr>
                      <td colSpan={3} className="py-10 text-center text-muted-foreground">
                        <Loader2 className="w-4 h-4 animate-spin text-hl mx-auto mb-1" />
                        <span>Chargement de l'équipe...</span>
                      </td>
                    </tr>
                  ) : (
                    team.map((member) => (
                      <tr key={member.id} className="hover:bg-slate-50/70 dark:hover:bg-raised/50 transition-colors">
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-hl/10 text-hl font-bold flex items-center justify-center text-xs">
                              {(member.full_name || member.email || 'U').substring(0, 2).toUpperCase()}
                            </div>
                            <div>
                              <p className="font-semibold text-foreground text-xs">{member.full_name || member.email}</p>
                              <p className="text-[10px] text-muted-foreground font-mono">{member.email}</p>
                            </div>
                          </div>
                        </td>

                        <td className="py-3 px-4">
                          <select
                            value={member.role}
                            onChange={(e) => handleUpdateRole(member.id, e.target.value)}
                            className="input-field !w-auto !py-1 !px-2.5 !text-[11px]"
                          >
                            <option value="owner">{t('company.role_owner')}</option>
                            <option value="conducteur_travaux">{t('company.role_site_manager')}</option>
                            <option value="chiffreur">{t('company.role_estimator')}</option>
                            <option value="member">{t('company.role_member')}</option>
                            <option value="read_only">{t('company.role_read_only')}</option>
                          </select>
                        </td>

                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => handleDeleteMember(member.id)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer"
                            title="Retirer"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pending Invites */}
            {invitations.length > 0 && (
              <div className="space-y-2 pt-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground font-mono">
                  Invitations en attente ({invitations.length})
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {invitations.map((inv) => (
                    <div key={inv.id} className="p-3 rounded-xl border border-line bg-card flex items-center justify-between text-xs shadow-xs">
                      <div>
                        <p className="font-semibold text-foreground">{inv.email}</p>
                        <p className="text-[10px] text-muted-foreground">Rôle : {inv.role}</p>
                      </div>
                      <button
                        onClick={() => {
                          const tokenVal = inv.invitation_token || inv.token || '';
                          const link = `${window.location.origin}/register?invitation=${tokenVal}`;
                          navigator.clipboard.writeText(link);
                          setCopiedToken(tokenVal);
                          setTimeout(() => setCopiedToken(null), 2000);
                        }}
                        className="flex items-center gap-1 text-[11px] text-hl font-bold hover:underline cursor-pointer"
                      >
                        <Copy className="w-3.5 h-3.5" />
                        <span>{copiedToken === (inv.invitation_token || inv.token) ? 'Copié !' : 'Copier lien'}</span>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

          </div>
        )}

        {/* ═══ TAB 3: WEB REFERENCES ═══ */}
        {activeTab === 'web' && (
          <div className="p-5 space-y-5 animate-fade-in-up">
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-foreground font-heading">Références & Veille Marchés Publics</h3>
              <p className="text-xs text-muted-foreground">Ajoutez les sites d'entreprises partenaires, de fournisseurs de matériaux ou de plateformes d'avis de marchés.</p>
            </div>

            {/* Add URL Form */}
            <form onSubmit={handleAddUrl} className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <input
                type="url"
                required
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                placeholder="https://www.ffbatiment.fr"
                className="input-field sm:col-span-2 !py-2 !text-xs"
              />
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newUrlLabel}
                  onChange={(e) => setNewUrlLabel(e.target.value)}
                  placeholder="Label (ex: Fédération FFB)"
                  className="input-field !py-2 !text-xs"
                />
                <button
                  type="submit"
                  disabled={isAddingUrl}
                  className="btn-primary !py-2 !px-3.5 !text-xs shrink-0 cursor-pointer"
                >
                  {isAddingUrl ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Ajouter'}
                </button>
              </div>
            </form>

            {/* URL Table */}
            <div className="border border-line rounded-2xl overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs">
                <thead className="bg-sunken border-b border-line text-muted-foreground font-semibold uppercase tracking-wider text-[10px]">
                  <tr>
                    <th className="py-3 px-4">Site Web & Référence</th>
                    <th className="py-3 px-4">Statut d'indexation</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {loadingUrls ? (
                    <tr>
                      <td colSpan={3} className="py-10 text-center text-muted-foreground">
                        <Loader2 className="w-4 h-4 animate-spin text-hl mx-auto mb-1" />
                        <span>Chargement des sites...</span>
                      </td>
                    </tr>
                  ) : referenceUrls.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="py-10 text-center text-muted-foreground">
                        Aucun site web ajouté.
                      </td>
                    </tr>
                  ) : (
                    referenceUrls.map((u) => (
                      <tr key={u.id} className="hover:bg-slate-50/70 dark:hover:bg-raised/50 transition-colors">
                        <td className="py-3 px-4">
                          <div>
                            <p className="font-semibold text-foreground text-xs">{u.label || u.url}</p>
                            <a
                              href={u.url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[11px] text-hl hover:underline flex items-center gap-1 font-mono mt-0.5"
                            >
                              <span>{u.url}</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                        </td>

                        <td className="py-3 px-4">
                          <span
                            className={
                              u.status === 'broken'
                                ? 'badge-pill-red text-[10px]'
                                : u.status === 'fetching'
                                ? 'badge-pill-amber text-[10px]'
                                : u.status === 'active'
                                ? 'badge-pill-emerald text-[10px]'
                                : 'badge-pill-slate text-[10px]'
                            }
                          >
                            {u.status === 'broken'
                              ? 'Erreur'
                              : u.status === 'fetching'
                              ? 'Récupération…'
                              : u.status === 'active'
                              ? 'Indexé'
                              : u.status}
                          </span>
                          {u.status === 'broken' && u.last_fetch_error && (
                            <p className="text-[10px] text-danger/80 mt-1 max-w-[240px] leading-snug">
                              {u.last_fetch_error}
                            </p>
                          )}
                        </td>

                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => handleRefreshUrl(u.id)}
                            disabled={refreshingUrlId === u.id}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-hl hover:bg-hl/10 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-wait mr-1"
                            title="Actualiser"
                          >
                            <RefreshCw className={`w-4 h-4 ${refreshingUrlId === u.id ? 'animate-spin' : ''}`} />
                          </button>
                          <button
                            onClick={() => handleDeleteUrl(u.id)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer"
                            title="Supprimer"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

          </div>
        )}

        {/* ═══ TAB 4: CE QUE L'IA A APPRIS DE VOTRE ENTREPRISE ═══ */}
        {activeTab === 'learnings' && (
          <div className="p-5 space-y-5 animate-fade-in-up">
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-foreground font-heading">Ce que l'application a appris de votre entreprise</h3>
              <p className="text-xs text-muted-foreground">
                Chaque fois qu'un marché est gagné ou perdu avec un retour de l'acheteur, ou qu'un ajustement est validé, l'application
                en tire un enseignement et le réutilise dans vos prochains dossiers. Vous pouvez le corriger ou le retirer si besoin.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-1.5">
              {[
                { id: 'all', label: 'Tous' },
                { id: 'planning', label: 'Planning' },
                { id: 'methodology', label: 'Méthodologie' },
                { id: 'qse', label: 'QSE / Environnement' },
                { id: 'safety', label: 'Sécurité' },
                { id: 'pricing', label: 'Tarification' },
                { id: 'general', label: 'Général' },
              ].map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setLearningCategoryFilter(cat.id)}
                  className={`px-3 py-1.5 rounded-xl text-[11px] font-semibold border transition-all cursor-pointer ${
                    learningCategoryFilter === cat.id
                      ? 'bg-hl text-hl-contrast border-hl shadow-xs'
                      : 'border-line text-muted-foreground hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-raised'
                  }`}
                >
                  {cat.label}
                </button>
              ))}
            </div>

            <div className="flex items-center justify-between">
              <button
                onClick={() => setShowNewLearningForm((v) => !v)}
                className="btn-secondary !py-1.5 !px-3 !text-[11px] cursor-pointer"
              >
                {showNewLearningForm ? <XCircle className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
                {showNewLearningForm ? 'Annuler' : 'Nouvel enseignement'}
              </button>
            </div>

            {showNewLearningForm && (
              <div className="border border-line rounded-xl p-4 space-y-2.5 bg-sunken/40">
                <input
                  value={newLearningForm.title}
                  onChange={(e) => setNewLearningForm({ ...newLearningForm, title: e.target.value })}
                  className="input-field !text-xs !font-bold"
                  placeholder="Titre bref (ex. : Toujours proposer un béton bas carbone en zone urbaine)"
                />
                <textarea
                  value={newLearningForm.actionable_directive}
                  onChange={(e) => setNewLearningForm({ ...newLearningForm, actionable_directive: e.target.value })}
                  className="input-field !text-xs"
                  rows={2}
                  placeholder="Consigne à appliquer désormais dans les prochains dossiers"
                />
                <div className="flex flex-wrap items-center gap-2.5">
                  <select
                    value={newLearningForm.category}
                    onChange={(e) => setNewLearningForm({ ...newLearningForm, category: e.target.value })}
                    className="input-field !text-[11px] !py-1.5 !w-auto"
                  >
                    <option value="general">Général</option>
                    <option value="planning">Planning</option>
                    <option value="methodology">Méthodologie</option>
                    <option value="qse">QSE / Environnement</option>
                    <option value="safety">Sécurité</option>
                    <option value="pricing">Tarification</option>
                  </select>

                  <div className="flex items-center rounded-lg border border-line overflow-hidden text-[11px] font-semibold">
                    <button
                      type="button"
                      onClick={() => setNewLearningForm({ ...newLearningForm, personal: false })}
                      className={`px-2.5 py-1.5 flex items-center gap-1 cursor-pointer transition-colors ${!newLearningForm.personal ? 'bg-hl text-hl-contrast' : 'text-muted-foreground hover:bg-slate-100 dark:hover:bg-raised'}`}
                      title="Visible par toute l'équipe"
                    >
                      <Users className="w-3 h-3" /> Collectif
                    </button>
                    <button
                      type="button"
                      onClick={() => setNewLearningForm({ ...newLearningForm, personal: true })}
                      className={`px-2.5 py-1.5 flex items-center gap-1 cursor-pointer transition-colors ${newLearningForm.personal ? 'bg-hl text-hl-contrast' : 'text-muted-foreground hover:bg-slate-100 dark:hover:bg-raised'}`}
                      title="Visible seulement par vous"
                    >
                      <User className="w-3 h-3" /> Personnel
                    </button>
                  </div>

                  <button
                    onClick={handleCreateLearning}
                    disabled={creatingLearning}
                    className="btn-primary !py-1.5 !px-3 !text-[11px] cursor-pointer ml-auto"
                  >
                    {creatingLearning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />} Enregistrer
                  </button>
                </div>
                <p className="text-[10px] text-muted-foreground">
                  {newLearningForm.personal
                    ? "Cet enseignement ne sera appliqué que pour vos propres générations, invisible pour le reste de l'équipe."
                    : "Cet enseignement s'appliquera à tous les prochains dossiers de toute l'équipe."}
                </p>
              </div>
            )}

            {loadingLearnings ? (
              <div className="py-12 text-center text-muted-foreground">
                <Loader2 className="w-5 h-5 animate-spin text-hl mx-auto mb-2" />
                <span>Chargement…</span>
              </div>
            ) : filteredLearnings.length === 0 ? (
              <div className="py-12 text-center text-muted-foreground space-y-2">
                <Brain className="w-8 h-8 text-slate-300 dark:text-zinc-600 mx-auto" />
                <p className="font-semibold text-foreground">Rien appris pour l'instant</p>
                <p className="text-[11px] max-w-sm mx-auto">
                  Dès qu'un dossier sera marqué gagné ou perdu avec un retour de l'acheteur, les enseignements apparaîtront ici.
                </p>
              </div>
            ) : (
              <div className="space-y-2.5">
                {filteredLearnings.map((l) => (
                  <div key={l.id} className={`border rounded-xl p-4 space-y-2.5 ${l.is_active ? 'border-line' : 'border-line opacity-60'}`}>
                    {editingLearningId === l.id ? (
                      <div className="space-y-2.5">
                        <input
                          value={editLearningForm.title}
                          onChange={(e) => setEditLearningForm({ ...editLearningForm, title: e.target.value })}
                          className="input-field !text-xs !font-bold"
                          placeholder="Titre"
                        />
                        <textarea
                          value={editLearningForm.learning_insight}
                          onChange={(e) => setEditLearningForm({ ...editLearningForm, learning_insight: e.target.value })}
                          className="input-field !text-xs"
                          rows={2}
                          placeholder="Ce qui a été observé"
                        />
                        <textarea
                          value={editLearningForm.actionable_directive}
                          onChange={(e) => setEditLearningForm({ ...editLearningForm, actionable_directive: e.target.value })}
                          className="input-field !text-xs"
                          rows={2}
                          placeholder="Directive appliquée dans les prochains dossiers"
                        />
                        <div className="flex justify-end gap-2">
                          <button onClick={() => setEditingLearningId(null)} className="btn-secondary !py-1.5 !px-3 !text-[11px] cursor-pointer">
                            <XCircle className="w-3.5 h-3.5" /> Annuler
                          </button>
                          <button
                            onClick={() => handleSaveLearning(l.id)}
                            disabled={savingLearningId === l.id}
                            className="btn-primary !py-1.5 !px-3 !text-[11px] cursor-pointer"
                          >
                            {savingLearningId === l.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />} Enregistrer
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-start gap-2.5 min-w-0">
                            <Brain className={`w-4 h-4 shrink-0 mt-0.5 ${l.is_active ? 'text-hl' : 'text-muted-foreground'}`} />
                            <div className="min-w-0">
                              <p className="text-xs font-bold text-foreground">{l.title}</p>
                              <div className="flex flex-wrap items-center gap-1.5 mt-1">
                                <span className="badge-pill text-[10px]">{getLearningCategoryLabel(l.category)}</span>
                                {l.created_by_user_id ? (
                                  <span className="badge-pill text-[10px] !bg-hl/10 !text-hl inline-flex items-center gap-1">
                                    <User className="w-2.5 h-2.5" /> Personnel
                                  </span>
                                ) : (
                                  <span className="badge-pill text-[10px] inline-flex items-center gap-1">
                                    <Users className="w-2.5 h-2.5" /> Équipe
                                  </span>
                                )}
                                <span className="text-[10px] text-muted-foreground">
                                  {l.source_outcome === 'won' ? 'Marché gagné' : l.source_outcome === 'lost' ? 'Marché perdu' : l.source_outcome === 'manual' ? 'Ajout manuel' : l.source_outcome}
                                  {' · '}{new Date(l.created_at).toLocaleDateString('fr-FR')}
                                </span>
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            <button
                              onClick={() => handleToggleLearningActive(l)}
                              className={`px-2 py-1 rounded-lg text-[10px] font-bold transition-colors cursor-pointer ${
                                l.is_active ? 'bg-positive/10 text-positive hover:bg-danger/10 hover:text-danger' : 'bg-sunken text-muted-foreground hover:bg-positive/10 hover:text-positive'
                              }`}
                              title={l.is_active ? 'Désactiver (ne plus utiliser)' : 'Réactiver'}
                            >
                              {l.is_active ? 'Actif' : 'Inactif'}
                            </button>
                            <button onClick={() => startEditLearning(l)} className="p-1.5 rounded-lg text-slate-400 hover:text-hl hover:bg-hl/10 transition-colors cursor-pointer" title="Modifier">
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => handleDeleteLearning(l.id)} className="p-1.5 rounded-lg text-slate-400 hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer" title="Supprimer">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                        <div className="pl-6 space-y-1">
                          <p className="text-[11px] text-muted-foreground"><span className="font-semibold text-foreground">Observé :</span> {l.learning_insight}</p>
                          <p className="text-[11px] text-muted-foreground"><span className="font-semibold text-foreground">Appliqué désormais :</span> {l.actionable_directive}</p>
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </div>

      {/* ─── UPLOAD MODAL (TAILGRIDS STYLE) ─── */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-card border border-line p-6 max-w-lg w-full rounded-2xl shadow-2xl space-y-4 animate-scale-in">
            <div className="flex items-center justify-between pb-3 border-b border-line">
              <h3 className="text-sm font-bold text-foreground font-heading flex items-center gap-2">
                <Upload className="w-4 h-4 text-hl" />
                <span>Ajouter un document au savoir-faire</span>
              </h3>
              <button
                type="button"
                onClick={() => setShowUploadModal(false)}
                className="text-muted-foreground hover:text-foreground text-xs font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAssetUpload} className="space-y-4">
              <div className="space-y-1 text-left">
                <label className="text-xs font-semibold text-foreground">{t('company.label_title_ref')}</label>
                <input
                  type="text"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  placeholder="Ex: Fiche technique béton bas carbone CEM III"
                  className="input-field !text-xs"
                />
              </div>

              <div className="space-y-1 text-left">
                <label className="text-xs font-semibold text-foreground">{t('company.label_category')}</label>
                <select
                  value={uploadCategory}
                  onChange={(e) => setUploadCategory(e.target.value)}
                  className="input-field !text-xs"
                >
                  <option value="fiche_technique">{t('company.cat_technical_sheet')}</option>
                  <option value="memoire_reference">{t('company.cat_past_proposal')}</option>
                  <option value="certification">{t('company.cat_certification')}</option>
                  <option value="qse_securite">{t('company.cat_qse_safety')}</option>
                  <option value="moyens_materiels">{t('company.cat_equipment_fleet')}</option>
                  <option value="autre">{t('company.cat_other')}</option>
                </select>
              </div>

              <div className="space-y-1 text-left">
                <label className="text-xs font-semibold text-foreground">{t('company.label_file')}</label>
                <div className="p-4 border-2 border-dashed border-line rounded-xl text-center space-y-2 hover:border-hl/50 transition-colors">
                  <Upload className="w-6 h-6 text-hl mx-auto" />
                  <p className="text-xs text-muted-foreground">Fichiers acceptés : PDF, Word (.docx)</p>
                  <input
                    type="file"
                    required
                    accept=".pdf,.docx,.doc"
                    onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    className="w-full text-xs text-muted-foreground file:mr-2 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-hl file:text-hl-contrast file:text-xs file:font-semibold file:cursor-pointer"
                  />
                  {uploadFile && (
                    <p className="text-xs text-positive font-bold truncate">
                      ✓ {uploadFile.name}
                    </p>
                  )}
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-line">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="btn-secondary !py-2 !px-3.5 !text-xs cursor-pointer"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={isUploadingAsset || !uploadFile}
                  className="btn-primary !py-2 !px-4 !text-xs cursor-pointer"
                >
                  {isUploadingAsset ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Importer et Indexer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── SHAREPOINT CONNECT MODAL ─── */}
      {showSpModal && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-card border border-line p-6 max-w-lg w-full rounded-2xl shadow-2xl space-y-4 animate-scale-in">
            <div className="flex items-center justify-between pb-3 border-b border-line">
              <h3 className="text-sm font-bold text-foreground font-heading flex items-center gap-2">
                <Cloud className="w-4 h-4 text-hl" />
                <span>Connecter SharePoint</span>
              </h3>
              <button
                type="button"
                onClick={() => setShowSpModal(false)}
                className="text-muted-foreground hover:text-foreground text-xs font-bold"
              >
                ✕
              </button>
            </div>

            <p className="text-[11px] text-muted-foreground -mt-2">
              Renseignez les identifiants de l'application Azure AD (App Registration) autorisée à lire votre site SharePoint. Ces informations sont chiffrées avant stockage.
            </p>

            <form onSubmit={handleConnectSharePoint} className="space-y-3">
              <div className="space-y-1 text-left">
                <label className="text-xs font-semibold text-foreground">URL du site SharePoint</label>
                <input
                  type="url"
                  required
                  value={spForm.site_url}
                  onChange={(e) => setSpForm({ ...spForm, site_url: e.target.value })}
                  placeholder="https://monentreprise.sharepoint.com/sites/Projets"
                  className="input-field !text-xs"
                />
              </div>
              <div className="space-y-1 text-left">
                <label className="text-xs font-semibold text-foreground">Dossier à suivre</label>
                <input
                  type="text"
                  value={spForm.selected_folder_path}
                  onChange={(e) => setSpForm({ ...spForm, selected_folder_path: e.target.value })}
                  placeholder="/"
                  className="input-field !text-xs"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1 text-left">
                  <label className="text-xs font-semibold text-foreground">ID de tenant Microsoft</label>
                  <input
                    type="text"
                    required
                    value={spForm.ms_tenant_id}
                    onChange={(e) => setSpForm({ ...spForm, ms_tenant_id: e.target.value })}
                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    className="input-field !text-xs font-mono"
                  />
                </div>
                <div className="space-y-1 text-left">
                  <label className="text-xs font-semibold text-foreground">ID client (App Registration)</label>
                  <input
                    type="text"
                    required
                    value={spForm.client_id}
                    onChange={(e) => setSpForm({ ...spForm, client_id: e.target.value })}
                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    className="input-field !text-xs font-mono"
                  />
                </div>
              </div>
              <div className="space-y-1 text-left">
                <label className="text-xs font-semibold text-foreground">Secret client</label>
                <input
                  type="password"
                  required
                  value={spForm.client_secret}
                  onChange={(e) => setSpForm({ ...spForm, client_secret: e.target.value })}
                  placeholder="••••••••••••••••"
                  className="input-field !text-xs font-mono"
                />
              </div>

              {spActionError && (
                <p className="text-[11px] text-danger bg-danger/5 border border-danger/20 rounded-lg p-2">{spActionError}</p>
              )}

              <div className="flex justify-end gap-2 pt-3 border-t border-line">
                <button
                  type="button"
                  onClick={() => setShowSpModal(false)}
                  className="btn-secondary !py-2 !px-3.5 !text-xs cursor-pointer"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={connectingSp}
                  className="btn-primary !py-2 !px-4 !text-xs cursor-pointer"
                >
                  {connectingSp ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Connecter et vérifier'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── INVITE MODAL (TAILGRIDS STYLE) ─── */}
      {showInviteModal && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-card border border-line p-6 max-w-md w-full rounded-2xl shadow-2xl space-y-4 animate-scale-in">
            <div className="flex items-center justify-between pb-3 border-b border-line">
              <h3 className="text-sm font-bold text-foreground font-heading flex items-center gap-2">
                <Mail className="w-4 h-4 text-hl" />
                <span>{t('company.modal_invite_title')}</span>
              </h3>
              <button
                type="button"
                onClick={() => setShowInviteModal(false)}
                className="text-muted-foreground hover:text-foreground text-xs font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSendInvite} className="space-y-4">
              <div className="space-y-1 text-left">
                <label className="text-xs font-semibold text-foreground">{t('company.label_email')}</label>
                <input
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="collaborateur@entreprise.fr"
                  className="input-field !text-xs"
                />
              </div>

              <div className="space-y-1 text-left">
                <label className="text-xs font-semibold text-foreground">{t('company.label_assigned_role')}</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as any)}
                  className="input-field !text-xs"
                >
                  <option value="conducteur_travaux">{t('company.role_site_manager')}</option>
                  <option value="chiffreur">{t('company.role_estimator')}</option>
                  <option value="owner">{t('company.role_owner')}</option>
                  <option value="member">{t('company.role_member')}</option>
                  <option value="read_only">{t('company.role_read_only')}</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-line">
                <button
                  type="button"
                  onClick={() => setShowInviteModal(false)}
                  className="btn-secondary !py-2 !px-3.5 !text-xs cursor-pointer"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingInvite}
                  className="btn-primary !py-2 !px-4 !text-xs cursor-pointer"
                >
                  {isSubmittingInvite ? 'Envoi...' : t('company.btn_send_invite')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DCE Chat Sidebar */}
      <DCEChatSidebar
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
        mode="company"
      />
    </div>
  );
}
