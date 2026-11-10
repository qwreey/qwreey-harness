"""harness-doctor 툴킷: web (JS/TS 웹 — astro, react, vite 등). **골격만 있다.**

감지만 하고 검사는 아직 내지 않는다. 실제 프로젝트(블로그 react/astro, vitrine)를 claude-doctor 로 가져와
감사한 뒤 CANDIDATES 를 하나씩 검사로 옮긴다. 판정 기준 자리는 references/toolkits/web.md.
"""
import json

NAME = "web"
TITLE = "Web (JS/TS)"
REFERENCE = "references/toolkits/web.md"
FRAMEWORKS = {"astro", "react", "vite", "next", "vue", "svelte", "@sveltejs/kit", "solid-js", "preact", "nuxt", "@remix-run/react"}
SOURCE_EXT = (".astro", ".tsx", ".jsx", ".vue", ".svelte")
SKIP_DIRS = {"node_modules", "dist", ".astro", ".next", ".svelte-kit", ".turbo"}
SIDE_EFFECT_WORDS = []  # 후보: npm publish, wrangler deploy, vercel --prod (실제 스킬을 본 뒤 정한다)

# 실제 프로젝트를 가져온 뒤 채울 검사 후보. 코드 이름은 예약만 해 둔다.
CANDIDATES = [
    ("WEB-LOCK", "패키지 매니저 lock 이 하나인가(package-lock/pnpm-lock/yarn.lock/bun.lockb 혼재), packageManager 필드와 맞는가"),
    ("WEB-TSSTRICT", "tsconfig 의 strict(와 noUncheckedIndexedAccess 등) 여부. extends 사슬을 따라가 본다"),
    ("WEB-LINT", "린터·포매터 설정(eslint/biome/prettier) 존재와 둘이 겹치는지"),
    ("WEB-CMDS", "빌드·테스트·타입검사 명령(package.json scripts)이 CLAUDE.md 에 적혀 있는가, 적힌 명령이 scripts 에 있는가"),
    ("WEB-NODEPIN", "node·패키지 매니저 버전 핀(mise.toml, .nvmrc, engines)과 형제 저장소 사이 불일치(D-05 와 같은 원칙)"),
    ("WEB-GENERATED", "생성물(dist, .astro, schema.d.ts)이 커밋되거나 rules paths 에 걸리는지"),
]


def _packages(ctx):
    for f in ctx.files:
        if (f == "package.json" or f.endswith("/package.json")) and "node_modules/" not in f:
            try:
                yield f, json.loads(ctx.read(ctx.repo / f) or "{}")
            except ValueError:
                continue


def detect(ctx):
    marks = []
    for f, pkg in _packages(ctx):
        deps = set(pkg.get("dependencies") or {}) | set(pkg.get("devDependencies") or {})
        hit = sorted(FRAMEWORKS & deps)
        if hit:
            marks.append(f"{f}: {', '.join(hit)}")
    n = sum(1 for f in ctx.files if f.endswith(SOURCE_EXT) and "node_modules/" not in f)
    if n:
        marks.append(f"{'/'.join(e[1:] for e in SOURCE_EXT)} {n}개")
    return marks


def check(ctx):
    """골격: 아직 아무 검사도 내지 않는다(CANDIDATES 참고)."""
    return
