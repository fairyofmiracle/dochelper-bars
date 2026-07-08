# Документы для индексации

В Git **не попадают** файлы `*.docx` и `*.pdf` из этой папки (см. `.gitignore`) — это материалы кейса АО «Барс Груп».

## Что положить сюда перед запуском

Скопируйте 4 документа из брифа хакатона:

1. `Functionalnie.docx`
2. `Komandirovka.docx`
3. `ReestrMebeli.docx`
4. `newbiePage.docx`

```powershell
# из корня репозитория, если docx в папке материалов:
.\scripts\copy_docs.ps1
```

## Индексация

```powershell
$env:QDRANT_URL="http://127.0.0.1:6333"
.\.venv\Scripts\python scripts\ingest.py --clear
```

После ingest в Qdrant появятся текстовые chunks и описания иллюстраций из docx.
