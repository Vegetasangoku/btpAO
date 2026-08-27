# Walkthrough — Traduction Intégrale du Wizard de Réponse (5 Étapes) & Cohérence Multilingue 100%

Toutes les étapes du parcours de réponse aux appels d'offres ont été intégralement reliées au moteur d'internationalisation.

---

## 1. Traduction Complète des 5 Étapes du Wizard (`/dashboard/wizard`)

Lorsque la langue anglaise (**EN**) ou arabe (**AR**) est sélectionnée, l'intégralité du tunnel de réponse passe instantanément dans la langue choisie :

| Étape | Français 🇫🇷 | English 🇬🇧 | العربية 🇸🇦 |
| :--- | :--- | :--- | :--- |
| **En-tête** | Tunnel de Réponse Guidé | Guided Tender Response Tunnel | مسار تقديم العرض الإرشادي |
| **Titre** | Répondre à un Appel d'Offres | Respond to a Tender | صياغة الرد على المناقصة |
| **Sous-titre** | 5 étapes claires de l'analyse des pièces à la compilation finale du dossier. | 5 clear steps from DCE specifications to final proposal compilation. | ٥ خطوات واضحة من تحليل المستندات حتى التصدير النهائي. |
| **Étape 1** | 1. Importer les pièces | 1. Upload Documents | ١. رفع المستندات |
| *Zone dépôt* | Cliquez ou glissez-déposez vos fichiers ici | Click or drag & drop your files here | انقر أو اسحب المستندات إلى هنا |
| *Bouton 1* | Continuer vers la vérification | Continue to Verification | المتابعة للتحقق من البيانات |
| **Étape 2** | 2. Vérifier les informations | 2. Verify Information | ٢. التحقق من البيانات |
| *Champs* | Intitulé du Marché, Acheteur Public, Réf & Lot | Tender Title, Public Buyer, Ref & Lot | اسم المناقصة، الجهة المشترية، المرجع |
| *Bouton 2* | Valider et passer à la rédaction | Confirm and Proceed to Drafting | تأكيد والانتقال للصياغة |
| **Étape 3** | 3. Rédiger le mémoire | 3. Draft Technical Proposal | ٣. صياغة المذكرة الفنية |
| *Bouton 3* | Générer un chapitre technique | Generate Technical Chapter | توليد فصل فني جديد |
| **Étape 4** | 4. Pièces administratives | 4. Administrative Forms | ٤. النماذج الإدارية |
| *Formulaires* | Formulaire DC1, DC2, DUME / MEA | DC1 Form, DC2 Form, ESPD / MEA | نماذج DC1، DC2، والنموذج الدولي |
| **Étape 5** | 5. Exporter et finaliser | 5. Export & Finalize | ٥. التصدير النهائي |
| *Bouton 5* | Télécharger le Mémoire Word (.docx) | Download Word Proposal (.docx) | تحميل المذكرة بصيغة وورد (.docx) |

---

## 2. Cohérence Globale

- **Zéro mélange de langue** : Chaque page (`/dashboard`, `/dashboard/projects`, `/dashboard/company`, `/dashboard/branding`, `/dashboard/settings`, `/dashboard/wizard`) change entièrement et instantanément lors d'un clic sur `FR`, `EN` ou `AR`.
- **Persistance** : Le choix de langue est conservé dans `localStorage` (`btp_language`) et dans les cookies (`btp_lang`).
