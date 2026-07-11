cat >> .gitignore << 'EOF'

# Proyecto AMAFE
.env
data/raw/*
!data/raw/.gitkeep
logs/*.jsonl
chroma_db/
EOF

git add .gitignore .env.example
git commit -m "chore: .env.example y .gitignore actualizado"