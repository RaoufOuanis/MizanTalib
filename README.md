# ميزان الطالب — MizanTalib

<p align="center">
  <img src="assets/logo.png" alt="MizanTalib Logo" width="140"/>
</p>

**ميزان الطالب** (MizanTalib) est une application de bureau développée en Python/Tkinter pour la gestion de la présence, de la participation et des notes des étudiants. Elle est destinée aux enseignants du cycle universitaire algérien (Licence / Master).

---

## ✨ Fonctionnalités

- **Gestion des classes** — Créer et organiser les classes par cycle, année, groupe, section et spécialité.
- **Gestion des étudiants** — Ajouter, modifier et supprimer les étudiants par classe.
- **Prise de présence par caméra** — Scanner les étudiants via la webcam (code-barres / QR code) avec OpenCV.
- **Types de séances** — Définir les matières et types de séances (cours, TD, TP…).
- **Suivi de participation** — Enregistrer la participation des étudiants lors de chaque séance.
- **Absences justifiées** — Gérer les absences avec justifications.
- **Exclusions** — Marquer les étudiants exclus selon le seuil d'absences.
- **Tests & Évaluations** — Enregistrer et consulter les notes des étudiants.
- **Rapports finaux** — Générer des rapports récapitulatifs par classe.
- **Archivage** — Archiver et restaurer les données de semestres précédents.
- **Multilingue** — Interface disponible en arabe (🇩🇿) et en anglais (🇬🇧) via gettext.
- **Administration sécurisée** — Mot de passe administrateur avec hachage SHA-256.
- **Build portable** — Créer un exécutable Windows autonome avec PyInstaller.

---

## 📸 Aperçu

> *Captures d'écran à ajouter ici.*

---

## 🛠️ Prérequis

- **Python 3.11+** (testé avec Python 3.11 sur Windows)
- **pip** (gestionnaire de paquets Python)
- Une **webcam** (optionnel, pour la fonctionnalité de scan caméra)

---

## 🚀 Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/RaoufOuanis/MizanTalib.git
cd MizanTalib
```

### 2. Créer un environnement virtuel (recommandé)

```bash
python -m venv .venv
```

Activer l'environnement :

- **Windows (PowerShell)** :
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- **Windows (CMD)** :
  ```cmd
  .venv\Scripts\activate.bat
  ```

### 3. Installer les dépendances

```bash
pip install pillow opencv-python pandas tkcalendar polib
```

### 4. Lancer l'application

```bash
python main.py
```

---

## 📦 Build portable (exécutable Windows)

Pour créer un exécutable autonome (.exe) :

```bash
pip install pyinstaller
python build_portable.py
```

L'exécutable sera généré dans le dossier `dist/MizanTalib/`.

---

## 📁 Structure du projet

```
MizanTalib/
├── main.py                  # Point d'entrée principal (splash screen)
├── app.py                   # Application principale Tkinter
├── db.py                    # Initialisation et gestion de la base SQLite
├── admin.py                 # Authentification administrateur
├── camera.py                # Module caméra / scanner (OpenCV)
├── center_window.py         # Utilitaire de centrage de fenêtre
├── tooltip.py               # Infobulles personnalisées
├── build_portable.py        # Script de build PyInstaller
├── MizanTalib.spec          # Spec file PyInstaller
├── assets/
│   ├── logo.png
│   ├── logo.ico
│   └── fonts/               # Polices embarquées (Tajawal, etc.)
├── i18n/
│   ├── __init__.py           # Module d'internationalisation
│   ├── messages.py           # Chaînes de traduction
│   └── locale/               # Fichiers .po / .mo (ar, en)
├── services/                 # Couche de services métier
│   ├── attendance_service.py
│   ├── student_service.py
│   ├── class_service.py
│   ├── archive_service.py
│   └── ...
├── tabs/                     # Onglets de l'interface
│   ├── attendance_tab.py
│   ├── students_tab.py
│   ├── classes_tab.py
│   ├── tests_tab.py
│   └── ...
├── DB plan/
│   └── erDiagram.mmd        # Diagramme ER (Mermaid)
└── tools/                    # Scripts utilitaires
```

---

## 🗄️ Base de données

L'application utilise **SQLite** (`attendance.db`) avec les tables principales :

| Table | Description |
|---|---|
| `classes` | Définition des classes (cycle, année, groupe…) |
| `students` | Liste des étudiants rattachés à une classe |
| `sessions` | Enregistrements de présence par séance |
| `session_types` | Types de séances (matière + type) |
| `tests` | Notes des évaluations |
| `excused_absences` | Absences justifiées |
| `exclusions` | Étudiants exclus |
| `settings` | Paramètres (mot de passe admin, classe active…) |

---

## 🌐 Langues

L'interface supporte **l'arabe** et **l'anglais**. La langue peut être changée depuis les paramètres de l'application. Les traductions sont gérées via `gettext` (fichiers `.po` / `.mo`).

---

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une *issue* ou une *pull request*.

---

## 📄 Licence

Ce projet est distribué sous licence **MIT**. Voir le fichier `LICENSE` pour plus de détails.

---

## 👤 Auteur

**Raouf Ouanis** — [GitHub](https://github.com/RaoufOuanis)
