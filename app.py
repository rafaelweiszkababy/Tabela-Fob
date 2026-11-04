                        caixa=caixa_inv_val,
                    )

                    # O botão "Calcular" NUNCA grava no Google Sheets.
                    # Somente "Calcular e Salvar" executa o salvamento.
                    if salvar_inverso:
                        ok = salvar_no_google_sheets(
                            fab_inv_final,
                            nome_inv_final,
                            fob_calculado,
                            qtd_inv,
                            peso_inv,
                            comp_inv,
                            larg_inv,
                            alt_inv,
                            pdv_dict,
                            canais_salvar=CANAIS_DISPONIVEIS,
                        )

                        if ok:
                            st.success(
                                "Cálculo realizado e salvo na planilha do Google Sheets com sucesso!"
                            )
                        else:
                            st.warning(
                                "O cálculo foi concluído, mas o salvamento no Google Sheets "
                                "não pôde ser confirmado."
                            )
                    else:
                        st.info(
                            "Cálculo realizado. O resultado não foi salvo no histórico."
                        )

                    st.subheader(
                        "Projeção de PDV para todos os Marketplaces com esse FOB:"
                    )
                    st.table(res_tabela)

            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Erro inesperado no cálculo inverso: {e}")

# ============================================================
# ABA 3 — HISTÓRICO
# ============================================================
with tab3:
    st.subheader("📊 Registros Gravados no Google Sheets")
    df_sheets = carregar_do_google_sheets()

    if df_sheets.empty:
        st.info("Aguardando os primeiros registros ou verificando conexão...")

    else:
        st.dataframe(df_sheets, use_container_width=True)

        csv = df_sheets.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Baixar Histórico em CSV",
            data=csv,
            file_name="historico_simulacoes_pdv.csv",
            mime="text/csv",
        )

        st.divider()
        st.subheader("🗑 Gerenciar / Excluir Registros")
        st.caption(
            "Selecione um ou vários registros abaixo e clique uma única vez em "
            '"Excluir selecionados". Os registros são removidos em ordem segura para preservar os IDs.'
        )

        ids_disponiveis = df_sheets["ID"].astype(int).tolist() if "ID" in df_sheets.columns else []

        ids_selecionados = st.multiselect(
            "Registros que deseja excluir:",
            options=ids_disponiveis,
            format_func=lambda x: (
                f"ID {x} — "
                f"{df_sheets.loc[df_sheets['ID'] == x, 'nome_produto'].iloc[0]}"
                if "nome_produto" in df_sheets.columns and not df_sheets.loc[df_sheets['ID'] == x].empty
                else f"ID {x}"
            ),
            key="ids_para_deletar",
        )

        col_del1, col_del2 = st.columns([2, 1])
        with col_del1:
            st.write(
                f"**{len(ids_selecionados)} registro(s) selecionado(s).**"
            )
        with col_del2:
            if st.button(
                "🗑️ Excluir selecionados",
                type="primary",
                disabled=not ids_selecionados,
                use_container_width=True,
            ):
                sucesso, erros = deletar_varios_do_google_sheets(ids_selecionados)

                if sucesso:
                    st.success(
                        f"{len(ids_selecionados)} registro(s) removido(s) com sucesso!"
                    )
                    st.rerun()
                else:
                    st.error(
                        "Não foi possível remover todos os registros. "
                        f"IDs com erro: {', '.join(map(str, erros))}."
                    )
