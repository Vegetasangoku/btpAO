'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';

export type Language = 'fr' | 'en' | 'ar';

interface Translations {
  [key: string]: {
    [lang in Language]: string;
  };
}

export const dictionary: Translations = {
  // Brand & General
  'app.name': { fr: 'btpAO', en: 'btpAO', ar: 'btpAO' },
  'app.badge': { fr: 'PRO', en: 'PRO', ar: 'احترافي' },
  'app.tagline': { fr: 'Marchés Publics & Privés', en: 'Public & Private Tenders', ar: 'المناقصات العامة والخاصة' },
  'app.logout': { fr: 'Déconnexion', en: 'Log out', ar: 'تسجيل الخروج' },
  'app.theme': { fr: 'Thème', en: 'Theme', ar: 'المظهر' },
  'app.language': { fr: 'Langue', en: 'Language', ar: 'اللغة' },

  // Navigation (6 Entries)
  'nav.main_menu': { fr: 'Menu Principal', en: 'Main Menu', ar: 'القائمة الرئيسية' },
  'nav.dashboard': { fr: 'Tableau de bord', en: 'Dashboard', ar: 'لوحة القيادة' },
  'nav.wizard': { fr: 'Répondre à un appel d’offres', en: 'Respond to a Tender', ar: 'الرد على مناقصة' },
  'nav.projects': { fr: 'Mes appels d’offres', en: 'My Tenders', ar: 'ملفات المناقصات' },
  'nav.company': { fr: 'Mon entreprise', en: 'My Company', ar: 'ملف الشركة' },
  'nav.branding': { fr: 'Modèles & mise en forme', en: 'Templates & Branding', ar: 'النماذج والتنسيق' },
  'nav.settings': { fr: 'Paramètres', en: 'Settings', ar: 'الإعدادات' },

  // Dashboard Page
  'dash.badge': { fr: 'Espace Conducteurs & Chiffreurs', en: 'Site Managers & Estimators Workspace', ar: 'مساحة مديري المشاريع والمقدرين' },
  'dash.title': { fr: 'Tableau de Bord des Réponses aux Marchés', en: 'Tender Response Dashboard', ar: 'لوحة متابعة الرد على المناقصات' },
  'dash.desc': { fr: 'Pilotez vos dossiers d’appels d’offres en cours, qualifiez les opportunités et compilez vos mémoires techniques sur-mesure.', en: 'Manage active tender dossiers, qualify opportunities, and compile customized technical proposals.', ar: 'إدارة ملفات المناقصات الجارية، تقييم الفرص وتجميع المذكرات الفنية المخصصة.' },
  'dash.btn_new': { fr: 'Répondre à un appel d’offres', en: 'Respond to a Tender', ar: 'تقديم عرض جديد' },
  'dash.btn_all': { fr: 'Tous mes dossiers', en: 'All My Dossiers', ar: 'كافة الملفات' },
  'dash.kpi_in_progress': { fr: 'Dossiers en cours', en: 'In-progress Dossiers', ar: 'الملفات قيد الإعداد' },
  'dash.kpi_completed': { fr: 'Dossiers finalisés', en: 'Completed Dossiers', ar: 'الملفات المكتملة' },
  'dash.kpi_active_model': { fr: 'Modèle Word actif', en: 'Active Word Template', ar: 'نموذج وورد الفعال' },
  'dash.kpi_deduced': { fr: 'Déduit de l\'historique', en: 'Deduced from History', ar: 'مستنتج من السوابق' },
  'dash.kpi_deduced_sub': { fr: 'Auto-suggéré pour vos exports', en: 'Auto-suggested for exports', ar: 'مقترح تلقائياً للتصدير' },
  'dash.kpi_knowledge': { fr: 'Savoir-faire indexé', en: 'Indexed Knowledge Base', ar: 'قاعدة الخبرات المفهرسة' },
  'dash.kpi_active_base': { fr: 'Base Entreprise Active', en: 'Active Corporate Base', ar: 'قاعدة بيانات الشركة النشطة' },
  'dash.kpi_proofs_sub': { fr: 'Citations et preuves vérifiées', en: 'Verified citations & evidence', ar: 'اقتباسات وإثباتات معتمدة' },
  'dash.recent_title': { fr: 'Dossiers d\'appels d\'offres récents', en: 'Recent Tender Dossiers', ar: 'أحدث ملفات المناقصات' },
  'dash.see_all': { fr: 'Voir tout', en: 'View all', ar: 'عرض الكل' },
  'dash.loading': { fr: 'Chargement des dossiers...', en: 'Loading tender files...', ar: 'جاري تحميل الملفات...' },
  'dash.empty_title': { fr: 'Aucun appel d\'offres en cours', en: 'No active tender dossier', ar: 'لا توجد مناقصات جارية' },
  'dash.empty_desc': { fr: 'Déposez un dossier CCTP pour lancer l\'analyse Go/No-Go et la rédaction assistée.', en: 'Upload tender specifications to start Go/No-Go analysis and assisted drafting.', ar: 'قم برفع دفتر الشروط لبدء تحليل القرار والصياغة الذكية.' },
  'dash.empty_btn': { fr: 'Démarrer un nouveau dossier', en: 'Start a New Dossier', ar: 'بدء ملف مناقصة جديد' },
  'dash.ready_badge': { fr: 'Prêts pour dépôt', en: 'Ready for submission', ar: 'جاهز للتقديم' },
  'dash.total_sub': { fr: 'au total', en: 'total', ar: 'إجمالاً' },
  'dash.quick_access': { fr: 'Accès Rapides & Configuration', en: 'Quick Access & Configuration', ar: 'الوصول السريع والإعدادات' },

  // Projects Page (Mes Appels d'Offres)
  'projects.badge': { fr: 'Historique & Suivi des Marchés', en: 'Tender History & Tracking', ar: 'سجل ومتابعة المناقصات' },
  'projects.title': { fr: 'Mes Appels d\'Offres', en: 'My Tender Proposals', ar: 'ملفات المناقصات' },
  'projects.desc': { fr: 'Retrouvez tous vos dossiers, suivez l\'avancement de la rédaction et téléchargez vos mémoires finalisés.', en: 'Access all tender files, track drafting progress, and download finalized technical offers.', ar: 'استعراض كافة العروض، متابعة تقدم الصياغة وتحميل المذكرات المكتملة.' },
  'projects.btn_new': { fr: 'Répondre à un appel d\'offres', en: 'New Tender Response', ar: 'الرد على مناقصة' },
  'projects.search_placeholder': { fr: 'Rechercher par titre, acheteur public, référence...', en: 'Search by title, public buyer, reference code...', ar: 'بحث بالعنوان، الجهة المعلنة، أو الرقم المرجعي...' },
  'projects.filter_all': { fr: 'Tous', en: 'All', ar: 'الكل' },
  'projects.filter_in_progress': { fr: 'En cours', en: 'In progress', ar: 'قيد الصياغة' },
  'projects.filter_completed': { fr: 'Finalisés', en: 'Completed', ar: 'المكتملة' },
  'projects.status_ready': { fr: '✓ Mémoire Prêt', en: '✓ Ready for Export', ar: '✓ العرض جاهز' },
  'projects.status_drafting': { fr: '⚡ En rédaction', en: '⚡ In Drafting', ar: '⚡ قيد الصياغة' },
  'projects.buyer': { fr: 'Acheteur', en: 'Buyer', ar: 'الجهة المشترية' },
  'projects.btn_gonogo': { fr: 'Score Go/No-Go', en: 'Go/No-Go Score', ar: 'تقييم الجدوى' },
  'projects.btn_planning': { fr: 'Phasage & Planning', en: 'Phasing & Schedule', ar: 'الجدول الزمني والمراحل' },
  'projects.btn_wizard': { fr: 'Reprendre le Wizard', en: 'Resume Wizard', ar: 'استئناف المعالج' },
  'projects.btn_download': { fr: 'Télécharger Word/PDF →', en: 'Download Word/PDF →', ar: 'تحميل وورد/PDF ←' },
  'projects.empty_title': { fr: 'Aucun dossier correspondant trouvé', en: 'No matching tender file found', ar: 'لم يتم العثور على ملفات مطابقة' },
  'projects.empty_btn': { fr: 'Créer une nouvelle réponse', en: 'Create New Proposal', ar: 'إنشاء رد جديد' },

  // Company Page (Mon Entreprise)
  'company.badge': { fr: 'Espace Entreprise Unifié', en: 'Unified Company Hub', ar: 'مساحة الشركة الموحدة' },
  'company.title': { fr: 'Mon Entreprise', en: 'My Company', ar: 'ملف الشركة' },
  'company.desc': { fr: 'Gérez en un seul endroit votre savoir-faire technique, les accès de votre équipe et vos sources web certifiées.', en: 'Centrally manage your technical knowledge base, team access, and verified web references.', ar: 'إدارة مركزية للخبرات الفنية، صلاحيات الفريق والمصادر المعتمدة.' },
  'company.tab_knowledge': { fr: '1. Savoir-faire & Documents', en: '1. Knowledge & Assets', ar: '١. الخبرات والمستندات' },
  'company.tab_team': { fr: '2. Équipe & Conducteurs', en: '2. Team & Engineers', ar: '٢. الفريق والمهندسون' },
  'company.tab_web': { fr: '3. Sites & Références web', en: '3. Web References', ar: '٣. المواقع والمراجع' },
  'company.add_doc_title': { fr: 'Ajouter un document de référence au savoir-faire', en: 'Add Reference Document to Knowledge Base', ar: 'إضافة مستند مرجعي إلى قاعدة الخبرات' },
  'company.label_title_ref': { fr: 'Titre ou référence', en: 'Title or Reference', ar: 'العنوان أو المرجع' },
  'company.placeholder_title': { fr: 'Ex : Fiche Référence Passerelle Bois 2025', en: 'Ex: Timber Footbridge Reference Sheet 2025', ar: 'مثال: بطاقة مشروع جسر المشاة ٢٠٢٥' },
  'company.label_category': { fr: 'Catégorie', en: 'Category', ar: 'الفئة' },
  'company.label_file': { fr: 'Fichier (.pdf, .docx)', en: 'File (.pdf, .docx)', ar: 'الملف (.pdf, .docx)' },
  'company.cat_technical_sheet': { fr: 'Fiche Technique / Matériaux', en: 'Technical Sheet / Materials', ar: 'بطاقة فنية / مواد' },
  'company.cat_past_proposal': { fr: 'Mémoire Technique Passé', en: 'Past Reference Proposal', ar: 'مذكرة فنية سابقة' },
  'company.cat_certification': { fr: 'Certification (Qualibat, ISO)', en: 'Certification (Qualibat, ISO)', ar: 'شهادات واعتمادات' },
  'company.cat_qse_safety': { fr: 'Politique QSE & Sécurité', en: 'HSE Policy & Safety', ar: 'سياسة السلامة والجودة والبيئة' },
  'company.cat_equipment_fleet': { fr: 'Parc Matériel & Engins', en: 'Equipment & Plant Fleet', ar: 'المعدات والآليات' },
  'company.indexed_docs': { fr: 'Documents & Savoir-faire Indexés', en: 'Indexed Knowledge & Documents', ar: 'المستندات وقاعدة الخبرات المفهرسة' },
  'company.empty_knowledge_title': { fr: 'Aucun document dans le savoir-faire', en: 'No documents in knowledge base', ar: 'لا توجد مستندات في قاعدة الخبرات' },
  'company.empty_knowledge_desc': { fr: 'Ajoutez vos mémoires passés et fiches techniques ci-dessus.', en: 'Add your past proposals and technical sheets above.', ar: 'أضف مذكراتك السابقة وبطاقاتك الفنية أعلاه.' },
  'company.team_title': { fr: 'Collaborateurs & Conducteurs de Travaux', en: 'Team Members & Site Managers', ar: 'فريق العمل ومديرو المشاريع' },
  'company.team_desc': { fr: 'Attribuez les rôles sur les dossiers d\'appels d\'offres.', en: 'Assign roles and permissions on tender files.', ar: 'تحديد الأدوار والصلاحيات على ملفات المناقصات.' },
  'company.invite_btn': { fr: 'Inviter un collaborateur', en: 'Invite Team Member', ar: 'دعوة عضو جديد' },
  'company.role_owner': { fr: 'Chef d\'Entreprise (Admin)', en: 'Company Owner (Admin)', ar: 'مدير الشركة (مسؤول)' },
  'company.role_site_manager': { fr: 'Conducteur de Travaux', en: 'Site Manager / Engineer', ar: 'مدير الموقع / المهندس' },
  'company.role_estimator': { fr: 'Ingénieur Études & Chiffrage', en: 'Quantity Surveyor / Estimator', ar: 'مهندس الدراسات والتسعير' },
  'company.role_member': { fr: 'Collaborateur Général', en: 'General Team Member', ar: 'عضو فريق عام' },
  'company.role_read_only': { fr: 'Observateur (Lecture Seule)', en: 'Observer (Read Only)', ar: 'مراقب (قراءة فقط)' },
  'company.modal_invite_title': { fr: 'Inviter un nouveau collaborateur', en: 'Invite a New Team Member', ar: 'دعوة عضو جديد للفريق' },
  'company.label_email': { fr: 'Adresse e-mail', en: 'Email Address', ar: 'البريد الإلكتروني' },
  'company.label_assigned_role': { fr: 'Rôle attribué', en: 'Assigned Role', ar: 'الدور المحدد' },
  'company.btn_send_invite': { fr: 'Envoyer l’invitation', en: 'Send Invitation', ar: 'إرسال الدعوة' },
  'company.pending_invites': { fr: 'Invitations en attente', en: 'Pending Invitations', ar: 'الدعوات المعلقة' },
  'company.copy_link': { fr: 'Copier le lien direct', en: 'Copy Direct Link', ar: 'نسخ الرابط المباشر' },
  'company.copied': { fr: 'Copié !', en: 'Copied!', ar: 'تم النسخ!' },
  'company.web_title': { fr: 'Sites d\'Entreprises & Références Externes Indexées', en: 'Company Websites & External Indexed References', ar: 'مواقع الشركة والمراجع الخارجية المفهرسة' },
  'company.web_desc': { fr: 'Ces URLs sont crawlées et vectorisées une seule fois pour enrichir les citations lors de la rédaction des mémoires, sans requêtes répétitives.', en: 'These URLs are crawled and vectorized once to enrich technical proposal citations without repeated scraping.', ar: 'تتم فهرسة هذه الروابط مرة واحدة لإثراء الاقتباسات الفنية دون تكرار.' },
  'company.placeholder_url': { fr: 'https://www.entreprise-btp.fr/nos-chantiers', en: 'https://www.company.com/our-projects', ar: 'https://www.company.com/projects' },
  'company.placeholder_url_label': { fr: 'Libellé (ex: Réalisations)', en: 'Label (e.g. Portfolio)', ar: 'التسمية (مثال: المشاريع)' },
  'company.btn_add_url': { fr: 'Ajouter le site', en: 'Add Website', ar: 'إضافة الموقع' },
  'company.empty_web_title': { fr: 'Aucune URL enregistrée', en: 'No registered URL', ar: 'لا توجد روابط مسجلة' },
  'company.empty_web_desc': { fr: 'Ajoutez le site de votre entreprise pour extraire vos chantiers emblématiques.', en: 'Add your company website to extract landmark construction projects.', ar: 'أضف موقع شركتك لاستخراج سوابق الأعمال والمشاريع المميزة.' },

  // Branding Page
  'branding.badge': { fr: 'Charte & Sortie Documentaire', en: 'Branding & Output Formatting', ar: 'الهوية البصرية والتنسيق' },
  'branding.title': { fr: 'Modèles & Mise en Forme', en: 'Templates & Document Styling', ar: 'النماذج والتنسيق الوثائقي' },
  'branding.desc': { fr: 'Configurez votre modèle Word type pour que tous vos mémoires techniques soient compilés selon votre identité visuelle d\'entreprise.', en: 'Configure your standard Word template so that all technical proposals match your corporate visual identity.', ar: 'إعداد نموذج وورد الرسمي للشركة لضمان توافق كافة المذكرات الفنية مع هويتكم البصرية.' },
  'branding.word_title': { fr: 'Modèle Word de l\'Entreprise (.docx)', en: 'Company Word Template (.docx)', ar: 'نموذج وورد الرسمي للشركة (.docx)' },
  'branding.word_desc': { fr: 'Déduit automatiquement de l\'historique ou téléversé par vos soins.', en: 'Auto-deduced from company history or custom uploaded.', ar: 'مستنتج تلقائياً من السوابق أو مرفوع يدوياً.' },
  'branding.default_model': { fr: 'Modèle Standard BTP', en: 'Standard Construction Template', ar: 'النموذج القياسي للبناء' },
  'branding.active_tag': { fr: 'Modèle Actif', en: 'Active Template', ar: 'النموذج الفعال' },
  'branding.default_tag': { fr: 'Gabarit par défaut', en: 'Default Layout', ar: 'القالب الافتراضي' },
  'branding.replace_label': { fr: 'Remplacer par un nouveau modèle Word (.docx)', en: 'Replace with new Word template (.docx)', ar: 'استبدال بنموذج وورد جديد (.docx)' },
  'branding.word_hint': { fr: 'Le fichier doit comporter vos styles de paragraphes et votre page de garde.', en: 'The document must include your corporate paragraph styles and cover page.', ar: 'يجب أن يحتوي الملف على أنماط الفقرات وصفحة الغلاف الرسمية.' },
  'branding.btn_upload_word': { fr: 'Enregistrer comme nouveau modèle officiel', en: 'Save as Official Corporate Template', ar: 'حفظ كنموذج رسمي معتمد' },
  'branding.palette_title': { fr: 'Couleurs & Logo d\'Entreprise', en: 'Corporate Colors & Logo', ar: 'ألوان وشعار الشركة' },
  'branding.palette_desc': { fr: 'Appliqués sur les tableaux récapitulatifs, planning et couverture.', en: 'Applied to summary tables, Gantt schedule, and cover pages.', ar: 'تطبق على جداول التكاليف، الجدول الزمني والغلاف.' },
  'branding.accent_label': { fr: 'Couleur d\'accentuation des tableaux et titres', en: 'Tables & headings primary accent color', ar: 'اللون الرئيسي للجداول والعناوين' },
  'branding.footer_label': { fr: 'Mention légale en pied de page', en: 'Footer legal disclaimer', ar: 'الإشعار القانوني أسفل الصفحات' },
  'branding.btn_save_options': { fr: 'Sauvegarder les options graphiques', en: 'Save Graphic Preferences', ar: 'حفظ الخيارات البصرية' },

  // Settings Page
  'settings.badge': { fr: 'Configuration Système', en: 'System Settings', ar: 'إعدادات النظام' },
  'settings.title': { fr: 'Paramètres', en: 'System Settings', ar: 'إعدادات النظام' },
  'settings.desc': { fr: 'Personnalisez l’apparence de la plateforme, vos règles économiques de chiffrage et vos quotas.', en: 'Customize UI appearance, language, economic costing rules, and quotas.', ar: 'تخصيص المظهر، اللغة، قواعد التسعير والحصص.' },
  'settings.tab_theme': { fr: '1. Apparence & Thème', en: '1. Appearance & Theme', ar: '١. المظهر والسمة' },
  'settings.tab_economic': { fr: '2. Règles Économiques', en: '2. Costing Rules', ar: '٢. القواعد الاقتصادية' },
  'settings.tab_billing': { fr: '3. Abonnement & Quotas', en: '3. Plan & Quotas', ar: '٣. الاشتراك والحصص' },
  'settings.tab_regional': { fr: '4. Préférences Régionales & Langue', en: '4. Regional & Language', ar: '٤. الإعدادات الإقليمية واللغة' },
  'settings.tab_rgpd': { fr: '5. Confidentialité RGPD', en: '5. GDPR Privacy', ar: '٥. الخصوصية وحماية البيانات' },

  // Wizard Page (Complete Translations)
  'wizard.badge': { fr: 'Tunnel de Réponse Guidé', en: 'Guided Tender Response Tunnel', ar: 'مسار تقديم العرض الإرشادي' },
  'wizard.title': { fr: 'Répondre à un Appel d’Offres', en: 'Respond to a Tender', ar: 'صياغة الرد على المناقصة' },
  'wizard.desc': { fr: '5 étapes claires de l\'analyse des pièces à la compilation finale du dossier.', en: '5 clear steps from DCE specifications to final proposal compilation.', ar: '٥ خطوات واضحة من تحليل المستندات حتى التصدير النهائي.' },
  'wizard.open_full_file': { fr: 'Ouvrir la fiche complète (Go/No-Go & Planning)', en: 'Open Full Dossier (Go/No-Go & Schedule)', ar: 'فتح الملف الكامل (تقييم الجدوى والجدول الزمني)' },
  'wizard.step1': { fr: '1. Importer les pièces', en: '1. Upload Documents', ar: '١. رفع المستندات' },
  'wizard.step2': { fr: '2. Vérifier les informations', en: '2. Verify Information', ar: '٢. التحقق من البيانات' },
  'wizard.step3': { fr: '3. Rédiger le mémoire', en: '3. Draft Technical Proposal', ar: '٣. صياغة المذكرة الفنية' },
  'wizard.step4': { fr: '4. Pièces administratives', en: '4. Administrative Forms', ar: '٤. النماذج الإدارية' },
  'wizard.step5': { fr: '5. Exporter et finaliser', en: '5. Export & Finalize', ar: '٥. التصدير النهائي' },

  // Step 1
  'wizard.step1_title': { fr: 'Étape 1 : Importer les pièces de la consultation', en: 'Step 1: Upload Tender Documents & Specs', ar: 'الخطوة ١: رفع مستندات المناقصة' },
  'wizard.step1_desc': { fr: 'Déposez le CCTP, le Règlement de Consultation (RC), le DPGF ou les plans (PDF, DOCX, ZIP jusqu\'à 50 Mo).', en: 'Upload the technical specs (CCTP), tender rules (RC), pricing breakdown (DPGF) or drawings (PDF, DOCX, ZIP up to 50MB).', ar: 'قم برفع دفتر الشروط الفنية، لائحة المناقصة، جدول الكميات أو المخططات (حتى ٥٠ ميغابايت).' },
  'wizard.drop_title': { fr: 'Cliquez ou glissez-déposez vos fichiers ici', en: 'Click or drag & drop your files here', ar: 'انقر أو اسحب المستندات إلى هنا' },
  'wizard.drop_formats': { fr: 'Formats acceptés : PDF, Word (.docx), Zip de pièces', en: 'Accepted formats: PDF, Word (.docx), Zip archive', ar: 'الصيغ المقبولة: PDF، Word (.docx)، أرشيف Zip' },
  'wizard.selected_files': { fr: 'Fichiers sélectionnés', en: 'Selected files', ar: 'الملفات المختارة' },
  'wizard.optional_title': { fr: 'Titre indicatif du dossier (optionnel si détecté depuis les fichiers)', en: 'Proposal title (optional if auto-detected from files)', ar: 'عنوان الملف (اختياري في حال تم استخراجه من المستندات)' },
  'wizard.label_strategic_directives': { fr: 'Consignes Stratégiques Générales (prioritaires sur l\'IA)', en: 'General Strategic Directives (overrides AI defaults)', ar: 'التوجيهات الاستراتيجية العامة (لها الأولوية على الذكاء الاصطناعي)' },
  'wizard.placeholder_strategic_directives': { fr: 'Ex : Marge de 15 %, refus du sous-traitant X, toujours mentionner la certification ISO 9001...', en: 'E.g.: 15% margin, exclude subcontractor X, always mention ISO 9001 certification...', ar: 'مثال: هامش ربح 15%، رفض المقاول من الباطن X، اذكر دائمًا شهادة ISO 9001...' },
  'wizard.help_strategic_directives': { fr: 'Ces consignes s\'appliquent en priorité sur l\'historique de vos anciens dossiers pour chaque génération IA de ce dossier.', en: 'These directives take priority over your historical proposal data for every AI generation in this file.', ar: 'تُطبَّق هذه التوجيهات كأولوية على بيانات ملفاتكم السابقة في كل عملية توليد بالذكاء الاصطناعي لهذا الملف.' },
  'wizard.title_placeholder': { fr: 'Ex : Réhabilitation de 42 logements sociaux — Lot 03 Gros Œuvre', en: 'Ex: Renovation of 42 Social Housing Units — Lot 03 Structural Works', ar: 'مثال: مشروع ترميم ٤٢ وحدة سكنية — البناء الهيكلي' },
  'wizard.extracting': { fr: 'Analyse et extraction en cours...', en: 'Analyzing and extracting data...', ar: 'جاري التحليل واستخراج البيانات...' },
  'wizard.btn_to_verification': { fr: 'Continuer vers la vérification', en: 'Continue to Verification', ar: 'المتابعة للتحقق من البيانات' },

  // Step 2
  'wizard.step2_title': { fr: 'Étape 2 : Vérifier les informations extraites du marché', en: 'Step 2: Verify Extracted Tender Information', ar: 'الخطوة ٢: مراجعة البيانات المستخرجة من المناقصة' },
  'wizard.step2_desc': { fr: 'Ces éléments ont été pré-remplis automatiquement à partir des pièces déposées. Ajustez-les au besoin.', en: 'These fields have been pre-filled automatically from uploaded documents. Adjust if needed.', ar: 'تمت تعبئة هذه الحقول تلقائياً من المستندات المرفوعة. يمكنك تعديلها.' },
  'wizard.label_market_title': { fr: 'Intitulé du Marché *', en: 'Tender Title *', ar: 'اسم المناقصة *' },
  'wizard.label_buyer': { fr: 'Acheteur Public / Maître d\'Ouvrage *', en: 'Public Buyer / Contracting Authority *', ar: 'الجهة المشترية / صاحب العمل *' },
  'wizard.label_ref_lot': { fr: 'Référence de la Consultation & Lot', en: 'Tender Reference & Lot Number', ar: 'الرقم المرجعي ورقم الحصة' },
  'wizard.placeholder_ref_lot': { fr: 'Ex : AO-2026-042 - Lot 02', en: 'Ex: TENDER-2026-042 - Lot 02', ar: 'مثال: AO-2026-042 - الحصة ٠٢' },
  'wizard.label_location': { fr: 'Localisation du Chantier', en: 'Site Location', ar: 'موقع المشروع' },
  'wizard.placeholder_location': { fr: 'Ex : Lyon (69003)', en: 'Ex: Paris / London', ar: 'مثال: باريس / الرياض' },
  'wizard.label_deadline': { fr: 'Date Limite de Remise des Plis', en: 'Submission Deadline', ar: 'الموعد النهائي لتقديم العروض' },
  'wizard.label_budget': { fr: 'Budget Estimatif HT (€)', en: 'Estimated Budget excl. VAT (€)', ar: 'الميزانية التقديرية (€)' },
  'wizard.placeholder_budget': { fr: 'Ex : 450000', en: 'Ex: 450000', ar: 'مثال: ٤٥٠٠٠٠' },
  'wizard.btn_back_docs': { fr: 'Retour aux pièces', en: 'Back to Documents', ar: 'الرجوع للمستندات' },
  'wizard.btn_to_drafting': { fr: 'Valider et passer à la rédaction', en: 'Confirm and Proceed to Drafting', ar: 'تأكيد والانتقال للصياغة' },

  // Step 3
  'wizard.step3_title': { fr: 'Étape 3 : Rédiger le mémoire technique', en: 'Step 3: Draft Technical Proposal', ar: 'الخطوة ٣: صياغة المذكرة الفنية' },
  'wizard.step3_desc': { fr: 'Sections rédigées à partir de vos fiches savoir-faire. Chaque source est citée, et tout manque est marqué [À COMPLÉTER] sans invention.', en: 'Sections generated from company knowledge base. All sources are cited with zero hallucination.', ar: 'أقسام مصاغة استناداً لخبرات الشركة مع توثيق كافة المصادر.' },
  'wizard.btn_generate_chapter': { fr: 'Générer un chapitre technique', en: 'Generate Technical Chapter', ar: 'توليد فصل فني جديد' },
  'wizard.generating': { fr: 'Génération assistée...', en: 'AI Drafting in progress...', ar: 'جاري التوليد بالذكاء الاصطناعي...' },
  'wizard.empty_sections_title': { fr: 'Aucun chapitre rédigé pour l\'instant', en: 'No chapters drafted yet', ar: 'لا توجد فصول مكتوبة حالياً' },
  'wizard.empty_sections_desc': { fr: 'Cliquez sur "Générer un chapitre technique" pour lancer la rédaction IA appuyée sur votre savoir-faire.', en: 'Click "Generate Technical Chapter" to start AI drafting powered by your knowledge base.', ar: 'انقر على "توليد فصل فني" لبدء الصياغة الذكية المعتمدة على خبراتك.' },
  'wizard.btn_back_info': { fr: 'Retour aux informations', en: 'Back to Information', ar: 'الرجوع للبيانات' },
  'wizard.btn_to_admin': { fr: 'Passer aux pièces administratives', en: 'Proceed to Administrative Forms', ar: 'الانتقال للنماذج الإدارية' },

  // Step 4
  'wizard.step4_title': { fr: 'Étape 4 : Compléter les formulaires administratifs (Candidature)', en: 'Step 4: Complete Administrative Forms (Bidding Eligibility)', ar: 'الخطوة ٤: استكمال النماذج الإدارية (أهلية العطاء)' },
  'wizard.step4_desc': { fr: 'Vérification des déclarations d\'aptitude, certificats et formulaires types (DC1, DC2, DUME).', en: 'Verification of compliance declarations, certificates, and standard forms (DC1, DC2, ESPD/DUME).', ar: 'التحقق من إقرارات الأهلية، الشهادات والنماذج القياسية.' },
  'wizard.dc1_title': { fr: 'Formulaire DC1', en: 'DC1 Form', ar: 'نموذج DC1' },
  'wizard.dc1_desc': { fr: 'Lettre de candidature et désignation du mandataire par le candidat.', en: 'Application letter and designation of candidate representative.', ar: 'خطاب التقديم وتفويض ممثل التحالف.' },
  'wizard.dc1_badge': { fr: 'Données SIRET pré-remplies', en: 'Company Registration ID Pre-filled', ar: 'بيانات السجل التجاري معبأة مسبقاً' },
  'wizard.dc2_title': { fr: 'Formulaire DC2', en: 'DC2 Form', ar: 'نموذج DC2' },
  'wizard.dc2_desc': { fr: 'Déclaration du candidat individuel ou du membre du groupement.', en: 'Declaration of individual candidate or joint venture member.', ar: 'إقرار المتقدم المنفرد أو عضو التحالف.' },
  'wizard.dc2_badge': { fr: 'Chiffre d\'affaires & effectifs validés', en: 'Revenue & Headcount Verified', ar: 'الإيرادات وحجم العمالة معتمدة' },
  'wizard.dume_title': { fr: 'DUME / MEA', en: 'ESPD / MEA', ar: 'النموذج الأوروبي / الدولي' },
  'wizard.dume_desc': { fr: 'Document Unique de Marché Européen ou formulaires régionaux internationaux.', en: 'European Single Procurement Document or international regional forms.', ar: 'وثيقة المشتريات الموحدة أو النماذج الدولية.' },
  'wizard.dume_badge': { fr: 'Conformité vérifiée', en: 'Compliance Verified', ar: 'تم التحقق من المطابقة' },
  'wizard.compliance_note': { fr: 'Les attestations d\'assurances décennales et de vigilance URSSAF sont synchronisées avec la fiche entreprise.', en: 'Decennial insurance and social security compliance certificates are synchronized with company profile.', ar: 'تمت مزامنة شهادات التأمين والامتثال الضريبي والعمالي مع ملف الشركة.' },
  'wizard.btn_back_drafting': { fr: 'Retour à la rédaction', en: 'Back to Drafting', ar: 'الرجوع للصياغة' },
  'wizard.btn_to_export': { fr: 'Valider le dossier et exporter', en: 'Validate and Proceed to Export', ar: 'اعتماد الملف والتصدير' },

  // Step 5
  'wizard.step5_title': { fr: 'Étape 5 : Exporter et finaliser le mémoire', en: 'Step 5: Export & Finalize Technical Proposal', ar: 'الخطوة ٥: تصدير واعتماد المذكرة الفنية' },
  'wizard.step5_desc': { fr: 'Compilation au format Word (.docx) avec votre charte graphique et sélection de la langue de sortie.', en: 'Compile into Word (.docx) format with your corporate styling and target output language.', ar: 'تجميع المذكرة بصيغة وورد (.docx) وفق الهوية البصرية واللغة المحددة.' },
  'wizard.applied_template': { fr: 'Modèle Word Appliqué', en: 'Applied Word Template', ar: 'نموذج وورد المطبق' },
  'wizard.deduced_tag': { fr: 'Déduit de l\'historique', en: 'Deduced from History', ar: 'مستنتج من السوابق' },
  'wizard.default_template_name': { fr: 'Gabarit Standard BTP Entreprise', en: 'Standard Construction Corporate Layout', ar: 'القالب القياسي لشركات المقاولات' },
  'wizard.template_reason': { fr: 'Modèle officiel retenu pour l’assemblage des styles.', en: 'Official layout selected for styling assembly.', ar: 'النموذج المعتمد لتنسيق الفقرات.' },
  'wizard.change_template_link': { fr: 'Changer de modèle dans Modèles & mise en forme →', en: 'Change template in Templates & Branding →', ar: 'تغيير النموذج من صفحة النماذج والتنسيق ←' },
  'wizard.output_language': { fr: 'Langue de Rédaction du Mémoire', en: 'Proposal Output Language', ar: 'لغة صياغة المذكرة الفنية' },
  'wizard.btn_back_admin': { fr: 'Retour aux pièces administratives', en: 'Back to Administrative Forms', ar: 'الرجوع للنماذج الإدارية' },
  'wizard.compiling': { fr: 'Compilation du mémoire...', en: 'Compiling technical proposal...', ar: 'جاري تجميع المذكرة...' },
  'wizard.btn_download_word': { fr: 'Télécharger le Mémoire Word (.docx)', en: 'Download Word Proposal (.docx)', ar: 'تحميل المذكرة بصيغة وورد (.docx)' },
  'wizard.advanced_export_link': { fr: 'Options d\'export avancées (PDF, MEA)', en: 'Advanced Export Options (PDF, MEA)', ar: 'خيارات التصدير المتقدمة (PDF، دولي)' },

  // Common Actions
  'common.save': { fr: 'Enregistrer', en: 'Save', ar: 'حفظ' },
  'common.cancel': { fr: 'Annuler', en: 'Cancel', ar: 'إلغاء' },
  'common.delete': { fr: 'Supprimer', en: 'Delete', ar: 'حذف' },
  'common.back': { fr: 'Retour', en: 'Back', ar: 'رجوع' },
  'common.next': { fr: 'Continuer', en: 'Next', ar: 'متابعة' },
  'common.download': { fr: 'Télécharger', en: 'Download', ar: 'تحميل' },
  'common.status_draft': { fr: 'Brouillon', en: 'Draft', ar: 'مسودة' },
  'common.status_in_progress': { fr: 'En cours', en: 'In progress', ar: 'قيد التنفيذ' },
  'common.status_completed': { fr: 'Terminé', en: 'Completed', ar: 'مكتمل' },

  // Editor Page (Mémoire Technique -- Batch 12, rollout i18n)
  'editor.sections_title': { fr: 'Sections du Mémoire', en: 'Proposal Sections', ar: 'أقسام المذكرة' },
  'editor.section.presentation_entreprise': { fr: "1. Présentation de l'Entreprise", en: '1. Company Presentation', ar: '١. تقديم الشركة' },
  'editor.section.references_similaires': { fr: '2. Références de Travaux Similaires', en: '2. Similar Project References', ar: '٢. مراجع أعمال مماثلة' },
  'editor.section.moyens_humains': { fr: '3. Moyens Humains & Encadrement', en: '3. Human Resources & Supervision', ar: '٣. الموارد البشرية والإشراف' },
  'editor.section.moyens_materiels': { fr: '4. Moyens Matériels & Engins', en: '4. Equipment & Machinery', ar: '٤. المعدات والآليات' },
  'editor.section.methodologie_phasage': { fr: '5. Méthodologie & Planning Prévisionnel', en: '5. Methodology & Projected Schedule', ar: '٥. المنهجية والجدول الزمني' },
  'editor.section.qualite_controle': { fr: '6. Démarche Qualité & Autocontrôle', en: '6. Quality Approach & Self-Inspection', ar: '٦. الجودة والفحص الذاتي' },
  'editor.section.securite_ppsps': { fr: '7. Sécurité, Prévention & PPSPS', en: '7. Safety, Prevention & Site Safety Plan', ar: '٧. السلامة والوقاية' },
  'editor.section.rse_environnement': { fr: '8. RSE, Déchets BTP & Bilan Carbone', en: '8. CSR, Construction Waste & Carbon Footprint', ar: '٨. المسؤولية البيئية والكربون' },
  'editor.section.sous_traitance': { fr: '9. Politique de Sous-Traitance', en: '9. Subcontracting Policy', ar: '٩. سياسة المقاولة من الباطن' },
  'editor.section.planning_gantt': { fr: '10. Planning Gantt Prévisionnel', en: '10. Projected Gantt Schedule', ar: '١٠. الجدول الزمني التقديري' },
  'editor.studio_visuals': { fr: 'Studio Visuels', en: 'Visuals Studio', ar: 'استوديو الرسوم البيانية' },
  'editor.generation_failed': { fr: 'Échec de génération', en: 'Generation Failed', ar: 'فشل التوليد' },
  'editor.generating': { fr: 'Génération en cours…', en: 'Generating…', ar: 'جاري التوليد…' },
  'editor.score_rc': { fr: 'Score RC : {score}%', en: 'RC Score: {score}%', ar: 'نتيجة RC: {score}%' },
  'editor.not_generated': { fr: 'Non générée', en: 'Not generated', ar: 'لم يتم التوليد' },
  'editor.optional_tag': { fr: 'opt.', en: 'opt.', ar: 'اختياري' },
  'editor.optional_note': { fr: 'Section optionnelle — peut être omise si non requise par le RC', en: 'Optional section — may be omitted if not required by the tender rules', ar: 'قسم اختياري — يمكن حذفه إذا لم يكن مطلوباً وفق دفتر الشروط' },
  'editor.gantt_note': { fr: 'Généré automatiquement (Python/Matplotlib) — voir aussi le Studio Visuels', en: 'Automatically generated (Python/Matplotlib) — also available in the Visuals Studio', ar: 'يُنشأ تلقائياً (Python/Matplotlib) — متوفر أيضاً في استوديو الرسوم البيانية' },
  'editor.generating_ai': { fr: 'Génération IA…', en: 'AI Generating…', ar: 'التوليد بالذكاء الاصطناعي…' },
  'editor.btn_generate_ai': { fr: "Générer avec l'IA", en: 'Generate with AI', ar: 'توليد بالذكاء الاصطناعي' },
  'editor.fallback_section_title': { fr: 'Section', en: 'Section', ar: 'القسم' },
  'editor.default_project_title': { fr: 'Projet BTP', en: 'Construction Project', ar: 'مشروع بناء' },
  'editor.fallback_failed_html': { fr: 'La génération automatique de cette section n\'a pas abouti (service de génération indisponible ou surchargé). Cliquez sur « Générer avec l\'IA » pour réessayer, ou rédigez cette section manuellement.', en: 'Automatic generation for this section did not complete (generation service unavailable or overloaded). Click "Generate with AI" to retry, or write this section manually.', ar: 'لم تكتمل عملية التوليد التلقائي لهذا القسم (الخدمة غير متوفرة أو محملة بشكل زائد). انقر على "توليد بالذكاء الاصطناعي" لإعادة المحاولة، أو قم بالصياغة يدوياً.' },
  'editor.fallback_generating_html': { fr: 'Génération automatique en cours à partir de votre base de connaissances (RAG)… Cela peut prendre jusqu\'à une minute.', en: 'Automatic generation in progress from your knowledge base (RAG)… This may take up to a minute.', ar: 'جارٍ التوليد التلقائي استناداً إلى قاعدة معارفكم (RAG)… قد يستغرق ذلك حتى دقيقة واحدة.' },
  'editor.fallback_empty_html': { fr: 'Cliquez sur "Générer avec l\'IA" ou commencez à rédiger...', en: 'Click "Generate with AI" or start writing...', ar: 'انقر على "توليد بالذكاء الاصطناعي" أو ابدأ الصياغة...' },
  'editor.badge_failed': { fr: 'Échec de la génération automatique — aucun score de conformité disponible. Réessayez ou rédigez manuellement.', en: 'Automatic generation failed — no compliance score available. Retry or write this section manually.', ar: 'فشل التوليد التلقائي — لا توجد نتيجة مطابقة متاحة. أعد المحاولة أو قم بالصياغة يدوياً.' },
  'editor.badge_generating': { fr: 'Génération en cours — le score de conformité RC sera calculé à la fin.', en: 'Generation in progress — the RC compliance score will be calculated once complete.', ar: 'التوليد قيد التنفيذ — سيتم احتساب نتيجة المطابقة عند الانتهاء.' },
  'editor.badge_score_prefix': { fr: 'Score de conformité RC : ', en: 'RC Compliance Score: ', ar: 'نتيجة مطابقة RC: ' },
  'editor.badge_score_warning': { fr: ' — Des critères RC manquent dans cette section. Régénérez ou complétez manuellement.', en: ' — Some tender criteria are missing from this section. Regenerate or complete it manually.', ar: ' — تنقص بعض معايير دفتر الشروط في هذا القسم. أعد التوليد أو أكمل يدوياً.' },
  'editor.badge_not_generated': { fr: 'Section non encore générée — aucun score de conformité pour l\'instant.', en: 'Section not yet generated — no compliance score available yet.', ar: 'لم يتم توليد هذا القسم بعد — لا توجد نتيجة مطابقة حالياً.' },
  'editor.tiptap.loading': { fr: "Chargement de l'éditeur WYSIWYG...", en: 'Loading WYSIWYG editor...', ar: 'جارٍ تحميل المحرر...' },
  'editor.tiptap.locked_badge': { fr: 'Validé & Verrouillé', en: 'Validated & Locked', ar: 'معتمد ومقفل' },
  'editor.tiptap.live_edits_subtitle': { fr: 'Modifications en direct • Conformité Règlement de Consultation (RC)', en: 'Live edits • Compliance with tender rules (RC)', ar: 'تعديلات مباشرة • مطابقة لدفتر الشروط (RC)' },
  'editor.tiptap.btn_copilot': { fr: 'Copilote IA BTP', en: 'BTP AI Copilot', ar: 'مساعد الذكاء الاصطناعي' },
  'editor.tiptap.btn_locked': { fr: 'Verrouillé (Validé)', en: 'Locked (Validated)', ar: 'مقفل (معتمد)' },
  'editor.tiptap.btn_validate': { fr: 'Valider Section', en: 'Validate Section', ar: 'اعتماد القسم' },
  'editor.tiptap.saving': { fr: 'Enregistrement...', en: 'Saving...', ar: 'جارٍ الحفظ...' },
  'editor.tiptap.btn_save': { fr: 'Sauvegarder', en: 'Save', ar: 'حفظ' },
  'editor.tiptap.learning_title': { fr: 'Modification significative détectée ({percent}%)', en: 'Significant change detected ({percent}%)', ar: 'تم رصد تعديل كبير ({percent}%)' },
  'editor.tiptap.learning_default_summary': { fr: 'Voulez-vous mémoriser cet ajustement ?', en: 'Would you like to remember this adjustment?', ar: 'هل ترغب بحفظ هذا التعديل؟' },
  'editor.tiptap.learning_scope_label': { fr: 'Portée :', en: 'Scope:', ar: 'النطاق:' },
  'editor.tiptap.scope_this_ao': { fr: 'Cette réponse AO uniquement', en: 'This tender response only', ar: 'هذا العرض فقط' },
  'editor.tiptap.scope_similar_aos': { fr: 'AOs similaires (même section)', en: 'Similar tenders (same section)', ar: 'مناقصات مماثلة (نفس القسم)' },
  'editor.tiptap.scope_all_future': { fr: 'Tous les futurs dossiers', en: 'All future dossiers', ar: 'كل الملفات المستقبلية' },
  'editor.tiptap.btn_memorize': { fr: 'Mémoriser cet apprentissage', en: 'Remember this learning', ar: 'حفظ هذا التعلم' },
  'editor.tiptap.btn_ignore': { fr: 'Ignorer', en: 'Ignore', ar: 'تجاهل' },
  'editor.tiptap.tt_bold': { fr: 'Gras', en: 'Bold', ar: 'عريض' },
  'editor.tiptap.tt_italic': { fr: 'Italique', en: 'Italic', ar: 'مائل' },
  'editor.tiptap.tt_underline': { fr: 'Souligné', en: 'Underline', ar: 'تسطير' },
  'editor.tiptap.tt_highlight': { fr: 'Surligner', en: 'Highlight', ar: 'تظليل' },
  'editor.tiptap.tt_h1': { fr: 'Titre H1', en: 'Heading H1', ar: 'عنوان H1' },
  'editor.tiptap.tt_h2': { fr: 'Titre H2', en: 'Heading H2', ar: 'عنوان H2' },
  'editor.tiptap.tt_h3': { fr: 'Titre H3', en: 'Heading H3', ar: 'عنوان H3' },
  'editor.tiptap.tt_bullet_list': { fr: 'Liste à puces', en: 'Bullet list', ar: 'قائمة نقطية' },
  'editor.tiptap.tt_ordered_list': { fr: 'Liste numérotée', en: 'Numbered list', ar: 'قائمة مرقمة' },
  'editor.tiptap.tt_insert_table': { fr: 'Insérer un tableau technique', en: 'Insert a technical table', ar: 'إدراج جدول تقني' },
  'editor.tiptap.tt_undo': { fr: 'Annuler', en: 'Undo', ar: 'تراجع' },
  'editor.tiptap.tt_redo': { fr: 'Rétablir', en: 'Redo', ar: 'إعادة' },
  'editor.tiptap.locked_overlay': { fr: 'Section validée et sécurisée juridiquement', en: 'Section validated and legally secured', ar: 'القسم معتمد ومؤمن قانونياً' },
  'editor.tiptap.compliance_label': { fr: 'Score de conformité DCE :', en: 'DCE compliance score:', ar: 'نتيجة مطابقة DCE:' },
  'editor.tiptap.compliance_default_note': { fr: 'Tous les sous-critères du Règlement de Consultation sont couverts.', en: 'All sub-criteria of the tender rules (RC) are covered.', ar: 'جميع المعايير الفرعية لدفتر الشروط مغطاة.' },
  'editor.tiptap.modal_title': { fr: 'Copilote IA BTP (Claude 3.5)', en: 'BTP AI Copilot (Claude 3.5)', ar: 'مساعد الذكاء الاصطناعي (Claude 3.5)' },
  'editor.tiptap.modal_subtitle': { fr: 'Affinement technique de la section', en: 'Technical refinement of the section', ar: 'تحسين تقني للقسم' },
  'editor.tiptap.quick_improvements': { fr: 'Améliorations rapides :', en: 'Quick improvements:', ar: 'تحسينات سريعة:' },
  'editor.tiptap.preset_engins': { fr: '🚜 Intégrer détails engins & rotation des banches', en: '🚜 Add equipment details & formwork rotation', ar: '🚜 إضافة تفاصيل المعدات ودوران القوالب' },
  'editor.tiptap.preset_rse': { fr: '🌿 Renforcer les engagements RSE & Déchets', en: '🌿 Strengthen CSR & waste commitments', ar: '🌿 تعزيز الالتزامات البيئية وإدارة النفايات' },
  'editor.tiptap.preset_dtu': { fr: '📐 Rendre 100% technique & citer normes DTU', en: '📐 Make 100% technical & cite DTU standards', ar: '📐 جعل النص تقنياً بالكامل مع ذكر معايير DTU' },
  'editor.tiptap.custom_prompt_label': { fr: 'Consigne personnalisée :', en: 'Custom instruction:', ar: 'تعليمات مخصصة:' },
  'editor.tiptap.custom_prompt_placeholder': { fr: "Ex : Ajoute un paragraphe sur la procédure de coulage par temps froid et les fiches d'autocontrôle du ferraillage...", en: 'E.g.: Add a paragraph on cold-weather concrete pouring procedures and rebar self-inspection sheets...', ar: 'مثال: أضف فقرة حول إجراءات صب الخرسانة في الطقس البارد وأوراق الفحص الذاتي لحديد التسليح...' },
  'editor.tiptap.btn_cancel': { fr: 'Annuler', en: 'Cancel', ar: 'إلغاء' },
  'editor.tiptap.ai_writing': { fr: 'Rédaction IA en cours...', en: 'AI writing in progress...', ar: 'جارٍ الصياغة بالذكاء الاصطناعي...' },
  'editor.tiptap.btn_regenerate_ai': { fr: "Régénérer avec l'IA", en: 'Regenerate with AI', ar: 'إعادة التوليد بالذكاء الاصطناعي' },
};

interface I18nContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  isRtl: boolean;
}

const I18nContext = createContext<I18nContextType>({
  language: 'fr',
  setLanguage: () => {},
  t: (key) => key,
  isRtl: false,
});

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<Language>('fr');

  useEffect(() => {
    const saved = localStorage.getItem('btp_language') as Language;
    if (saved && (saved === 'fr' || saved === 'en' || saved === 'ar')) {
      setLanguageState(saved);
      document.documentElement.dir = saved === 'ar' ? 'rtl' : 'ltr';
      document.documentElement.lang = saved;
    }
  }, []);

  function setLanguage(lang: Language) {
    setLanguageState(lang);
    localStorage.setItem('btp_language', lang);
    document.cookie = `btp_lang=${lang}; path=/; max-age=31536000`;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
    document.documentElement.lang = lang;
  }

  function t(key: string, vars?: Record<string, string | number>): string {
    const entry = dictionary[key];
    let str = entry ? (entry[language] || entry['fr'] || key) : key;
    if (vars) {
      for (const [varKey, varValue] of Object.entries(vars)) {
        str = str.split(`{${varKey}}`).join(String(varValue));
      }
    }
    return str;
  }

  const isRtl = language === 'ar';

  return (
    <I18nContext.Provider value={{ language, setLanguage, t, isRtl }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useTranslation() {
  return useContext(I18nContext);
}
