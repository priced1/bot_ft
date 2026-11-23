import asyncio
import os
import calendar
import re
import requests
import urllib.parse
from getpass import getpass
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from datetime import datetime

# Carrega as variáveis do arquivo .env
load_dotenv()

IDS_CONTAS = ["BEATRIZ", "JHONATA", "ISABELLA"]

CONTAS = [
    {
        "id_conta": cid,
        "usuario": os.getenv(f"FT_USER_{cid}"),
        "senha": os.getenv(f"FT_SENHA_{cid}"),
        "senha_bot": os.getenv(f"SENHA_BOT_{cid}"),
        "auth_file": f"auth_{cid.lower()}.json",
        "nome_alvo": os.getenv(f"FT_NOME_{cid}", cid),
        "id_checkbox": os.getenv(f"FT_CHECKBOX_{cid}"),
    }
    for cid in IDS_CONTAS
]

# CONFIGURAÇÃO DE LOG DE HORARIO 
def log(tag, mensagem):
    hora = datetime.now().strftime("%H:%M:%S")
    print(f"[{hora}] {tag} {mensagem}")

async def rodar_bot(browser, conta):
    tag = f"[{conta['id_conta']} - {conta['nome_alvo']}]"
    inicio_bot = datetime.now()
    
    try:
        context_args = {}
        if os.path.exists(conta["auth_file"]):
            context_args["storage_state"] = conta["auth_file"]
            
        context = await browser.new_context(**context_args)
        page = await context.new_page()
        
        log(tag, "Abrindo página de login...")
        
        await page.goto(
            "https://www.fieltorcedor.com.br/auth/login/",
            timeout=60000,
            wait_until="domcontentloaded"
        )
        await page.evaluate("document.body.style.zoom = '75%'")

        try:
            await page.wait_for_selector('input[name="username"]', state="visible", timeout=5000)
            await page.fill('input[name="username"]', conta["usuario"])
            await page.fill('input[name="password"]', conta["senha"])
            log(tag, "Campos de login preenchidos.")

            botao_login = page.locator("#login-btn")
            await botao_login.wait_for(state="visible", timeout=5000)
            log(tag, "⚡ Clicando em 'ENTRAR COM FIEL'...")
            await botao_login.click()

        except Exception as e:
            log(tag, f"⚠️ Não foi possível realizar o login automático: {e}")
            log(tag, "Faça o login manual nesta aba.")

        log(tag, "Aguardando confirmação do login...")
        login_confirmado = False

        while not login_confirmado:
            try:
                current_url = page.url.lower()
                campos_login = await page.locator('input[name="username"]').count()

                if campos_login > 0:
                    log(tag, "⏳ Ainda na tela de login...")
                else:
                    botao_ingressos = page.locator('button.menu-item.ingressos')
                    if await botao_ingressos.count() > 0 and await botao_ingressos.is_visible():
                        login_confirmado = True
                        log(tag, "✅ Login confirmado pelo menu!")
                        break
                    if any(termo in current_url for termo in ["minha-conta", "/ingressos/", "/jogos/"]):
                        login_confirmado = True
                        log(tag, f"✅ Login confirmado pela URL: {current_url}")
                        break
            except Exception:
                pass
            await asyncio.sleep(1)

        try:
            await context.storage_state(path=conta["auth_file"])
            log(tag, "💾 Sessão salva com sucesso.")
        except Exception as e:
            log(tag, f"⚠️ Não foi possível salvar a sessão: {e}")

        log(tag, "Navegando para a aba de jogos...")

        try:
            await page.click('button.menu-item.ingressos', timeout=3000)
            await asyncio.sleep(0.5)
            await page.click('a.submenu-item[href="/jogos/"]', timeout=3000)
            await page.evaluate("document.body.style.zoom = '75%'")
        except Exception:
            await page.goto("https://www.fieltorcedor.com.br/jogos/", timeout=60000)
            await page.evaluate("document.body.style.zoom = '75%'")

        log(tag, f"⏳ Procurando pelo jogo com o filtro '{conta['termo_busca_jogo']}'...")
        while True:
            try:
                current_url = page.url
                if "setores" in current_url:
                    await page.evaluate("document.body.style.zoom = '70%'")
                    log(tag, f"🎯 Página de setores detectada: {current_url}")
                    break
                
                jogos_cards = page.locator('div.item')
                count = await jogos_cards.count()
                await page.evaluate("document.body.style.zoom = '70%'")
                
                encontrou_e_clicou = False
                for i in range(count):
                    card = jogos_cards.nth(i)
                    texto_card = await card.inner_text()
                    
                    if conta["termo_busca_jogo"].upper() in texto_card.upper():
                        log(tag, "🏟️ Jogo alvo encontrado na lista!")
                        botao_compre = card.locator('a.btn-primary:has-text("COMPRE AGORA")')
                        if await botao_compre.count() > 0 and await botao_compre.is_visible():
                            log(tag, "⚡ Clicando automaticamente em 'COMPRE AGORA'...")
                            await botao_compre.click()
                            encontrou_e_clicou = True
                            break
                
                card_minha_vida = page.locator('div.meuplano-card.mv:has-text("Minha Vida")')
                botao_comprar_plano = card_minha_vida.locator('p.btn.btn-link')
                if await botao_comprar_plano.count() > 0 and await botao_comprar_plano.is_visible():
                    log(tag, "⚡ Clicando automaticamente no 'Comprar' do plano...")
                    await botao_comprar_plano.click()
                    await asyncio.sleep(1)

                if encontrou_e_clicou:
                    await asyncio.sleep(2)
                    continue

            except Exception:
                pass

            await asyncio.sleep(2)
            try:
                await page.reload(timeout=5000)
            except:
                pass

        log(tag, "🚀 Conta entrou no evento, iniciando o sniper...")
        while True:
            try:
                current_url = page.url
                if "setores" not in current_url:
                    await page.evaluate("document.body.style.zoom = '70%'")
                    await asyncio.sleep(1)
                    continue

                setor_alvo = None
                for id_s in conta["setores_desejados"]:
                    selector = f'a:has(g#{id_s}:not(.disabled))'
                    if await page.query_selector(selector):
                        log(tag, f"🚨🚨🚨SETOR {id_s.upper()} LIBEROU!🚨🚨🚨")
                        setor_alvo = await page.query_selector(selector)
                        break
                
                if setor_alvo:
                    await setor_alvo.click()
                    log(tag, "🎟️ Iniciando reserva...")
                    await page.wait_for_selector('label[for="id_mode_0"]', timeout=10000)
                    await page.click('label[for="id_mode_0"]')
                    await asyncio.sleep(0.3)
                    await page.click('button:has-text("Prosseguir")')

                    log(tag, f"👤 Marcando dependente/opção {conta['nome_alvo']}...")
                    await page.wait_for_selector(conta["id_checkbox"], timeout=10000)
                    await page.check(conta["id_checkbox"])
                    await asyncio.sleep(0.2)
                    await page.click("#submit_fieltorcedor_booking_by_dependente_form")

                    log(tag, "👤 Selecionando o nome na lista de atribuição...")
                    await page.wait_for_selector('select[name="attendee_membership"]', timeout=10000)
                    
                    select_locator = page.locator('select[name="attendee_membership"]')
                    opcoes_validas = select_locator.locator('option:not([disabled])')
                    qtd_opcoes = await opcoes_validas.count()
                    
                    if qtd_opcoes > 0:
                        primeiro_valor = await opcoes_validas.nth(0).get_attribute("value")
                        text_opcao = await opcoes_validas.nth(0).inner_text()
                        log(tag, f"👤 Selecionando automaticamente: '{text_opcao}'")
                        await select_locator.select_option(value=primeiro_valor)
                    else:
                        print(f"{tag} ⚠️ Nenhuma opção válida encontrada no select!")

                    await asyncio.sleep(0.5)
                    log(tag, "🎟️ Clicando em 'Atribuir Ingresso'...")
                    await page.click('button[type="submit"][name="action"]:has-text("Atribuir Ingresso")')
                    await asyncio.sleep(1.5)

                    log(tag, "⏳ Aguardando botão 'Continuar' ficar habilitado...")   
                    botao_continuar = page.locator('a#confirmation:has-text("Continuar")')
                    await botao_continuar.wait_for(state="visible", timeout=10000)
                    
                    try:
                        await page.wait_for_selector('a#confirmation[aria-disabled="false"]', timeout=5000)
                    except:
                        pass
                    
                    await asyncio.sleep(0.5)
                    log(tag, "⚡ Clicando em 'Continuar'...")
                    await botao_continuar.click()
                  
                    fim_bot = datetime.now()
                    tempo_total = fim_bot - inicio_bot
                    log(tag, f"⏱️ Tempo total do processo: {str(tempo_total).split('.')[0]}")
                    break

                await asyncio.sleep(1)
                await page.reload(timeout=10000)

            except Exception:
                await asyncio.sleep(1)
                try:
                    await page.reload(timeout=5000)
                except:
                    pass
                continue
        
        await asyncio.sleep(1800)

    except Exception as erro_sessao:
        log(tag, f"⚠️ A sessão sofreu uma interrupção: {erro_sessao}")


async def main():
    print("========================================")
    print("      CONFIGURAÇÃO DO BOT - FIEL")
    print("========================================")
    print("Usuários disponíveis:")

    for idx, conta in enumerate(CONTAS, 1):
        print(f"  {idx} - {conta['id_conta']} ({conta['nome_alvo']})")

    escolha_usuario = input(
        "\nSelecione o(s) número(s) do(s) usuário(s) "
        "separado(s) por vírgula (ex: 1 ou 1,2): "
    ).strip()

    contas_candidatas = []

    try:
        indices = [int(x.strip()) - 1 for x in escolha_usuario.split(",") if x.strip()]
        indices_unicos = list(dict.fromkeys(indices))
        contas_candidatas = [
            CONTAS[i] for i in indices_unicos if 0 <= i < len(CONTAS)
        ]
    except Exception:
        print("❌ Seleção inválida! Digite apenas os números correspondentes aos usuários.")
        return

    if not contas_candidatas:
        print("❌ Nenhuma conta válida selecionada. Encerrando.")
        return

    # ==========================================================
    # VALIDAÇÃO DE SENHA POR USUÁRIO SELECIONADO
    # ==========================================================
    print("\n========================================")
    print("       AUTENTICAÇÃO DE USUÁRIOS")
    print("========================================")
    
    contas_selecionadas = []
    campos_obrigatorios = ["usuario", "senha", "senha_bot", "nome_alvo", "id_checkbox"]

    for conta in contas_candidatas:
        faltando = [campo for campo in campos_obrigatorios if not conta.get(campo)]
        if faltando:
            print(f"❌ Erro de configuração no .env para {conta['id_conta']}: faltando {', '.join(faltando)}.")
            continue

        senha_correta = conta["senha_bot"]

        for tentativa in range(1, 4):
            senha_digitada = getpass(
                f"🔑 Digite a senha de acesso para {conta['id_conta']} ({conta['nome_alvo']}): "
            ).strip()

            if senha_digitada == senha_correta:
                print(f"✅ Acesso liberado para {conta['id_conta']}!\n")
                contas_selecionadas.append(conta)
                break
            else:
                restantes = 3 - tentativa
                if restantes > 0:
                    print(f"❌ Senha incorreta! Tentativas restantes: {restantes}")
                else:
                    print(f"🚫 Limite de tentativas excedido para {conta['id_conta']}. Usuário ignorado.\n")

    if not contas_selecionadas:
        print("❌ Nenhuma conta foi autenticada com sucesso. Encerrando o bot.")
        return

    print("\n========================================")
    print("           SELEÇÃO DO JOGO")
    print("========================================")
    print("1 - TECLE 1 PARA INFORMAR O RIVAL")
    print("========================================")

    while True:
        opcao_jogo = input("\n🎯 Escolha uma opção (1): ").strip()
        if opcao_jogo in ("1",):
            break
        print("❌ Digite somente 1.")

    if opcao_jogo == "1":
        while True:
            rival = input("\n⚽ Digite o nome do rival: ").strip()
            if rival:
                break
            print("❌ Digite o nome de um rival válido.")

        novo_termo = rival.upper()
        jogo_selecionado = {
            "mandante": "Corinthians",
            "visitante": rival.upper(),
            "data": "Manual",
            "hora": "Manual",
            "estadio": "Neo Química Arena",
            "competicao": "Manual",
            "rodada": "",
            "termo_busca": novo_termo
        }

    print("\n========================================")
    print("           SELEÇÃO DE SETORES")
    print("========================================")
    print("1 - Procurar somente NORTE")
    print("2 - Procurar somente SUL")
    print("3 - Procurar NORTE E SUL")
    print("========================================")

    while True:
        opcao_setor = input("\n🎯 Escolha o setor (1, 2 ou 3): ").strip()
        if opcao_setor == "1":
            setores_escolhidos = ["norte"]
            break
        elif opcao_setor == "2":
            setores_escolhidos = ["sul"]
            break
        elif opcao_setor == "3":
            setores_escolhidos = ["norte", "sul"]
            break
        else:
            print("❌ Opção inválida. Digite 1, 2 ou 3.")

    for conta in contas_selecionadas:
        conta["termo_busca_jogo"] = novo_termo
        conta["setores_desejados"] = setores_escolhidos.copy()

    print(f"\n🚀 Iniciando o bot para {len(contas_selecionadas)} conta(s)")
    print(f"🎯 Jogo alvo: Corinthians x {jogo_selecionado['visitante']}")
    print(f"📅 Data: {jogo_selecionado['data']}")
    print(f"⏰ Horário: {jogo_selecionado['hora']}")
    print(f"🏟️ Estádio: {jogo_selecionado['estadio']}")
    print(f"🔎 Termo de busca: '{novo_termo}'\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome")
        await asyncio.gather(
            *(rodar_bot(browser, conta) for conta in contas_selecionadas),
            return_exceptions=True
        )
        await browser.close()

asyncio.run(main())