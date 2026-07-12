/* eslint-disable react/jsx-key -- ячейки таблиц/данные рендерятся внутри keyed .map() в DocKit */
import type { Metadata } from "next";
import {
  Mic, Search, FolderKanban, Brain, Zap, GitBranch, Wallet, Bot,
  FileText, Globe, ScrollText, Star,
} from "lucide-react";
import { DocLayout, type DocGroup } from "@/components/docs/DocLayout";
import {
  DocSection, Lead, P, H3, IC, Kbd, A, UL, LI, Steps, Step, Callout,
  FeatureGrid, FeatureCard, DataTable,
} from "@/components/docs/DocKit";
import { getTranslations } from "next-intl/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("docs");
  return {
    title: t("metaTitle"),
    description: t("metaDescription"),
  };
}

// GROUPS — статическая JSX-структура (не может звать t() на уровне модуля),
// поэтому обёрнута в функцию, вызываемую внутри async-компонента страницы
// с уже полученным `t` (next-intl/server, getTranslations("docs")). Тот же
// паттерн, что buildGroups(t) в app/api-docs/page.tsx.
function buildGroups(t: Awaited<ReturnType<typeof getTranslations>>): DocGroup[] {
  return [
  {
    title: t("intro.groupTitle"),
    items: [
      {
        id: "overview",
        label: t("intro.overviewLabel"),
        content: (
          <>
            <DocSection title={t("intro.overviewTitle")}>
              <Lead>{t("intro.overviewLead")}</Lead>
              <P>{t("intro.overviewWaysP")}</P>
              <FeatureGrid>
                <FeatureCard icon={<Globe size={16} />} title={t("intro.overviewWebTitle")}>
                  {t("intro.overviewWebBody")}
                </FeatureCard>
                <FeatureCard icon={<Bot size={16} />} title={t("intro.overviewBotTitle")}>
                  {t.rich("intro.overviewBotBody", { a: (chunks) => <A href="https://t.me/aineron_bot">{chunks}</A> })}
                </FeatureCard>
                <FeatureCard icon={<Zap size={16} />} title={t("intro.overviewApiTitle")}>
                  {t.rich("intro.overviewApiBody", { a: (chunks) => <A href="/api-docs/">{chunks}</A> })}
                </FeatureCard>
              </FeatureGrid>
            </DocSection>
            <DocSection title={t("intro.diffTitle")}>
              <UL>
                <LI>{t.rich("intro.diffItem1", { b: (chunks) => <b>{chunks}</b> })}</LI>
                <LI>{t.rich("intro.diffItem2", { b: (chunks) => <b>{chunks}</b> })}</LI>
                <LI>{t.rich("intro.diffItem3", { b: (chunks) => <b>{chunks}</b> })}</LI>
                <LI>{t.rich("intro.diffItem4", { b: (chunks) => <b>{chunks}</b> })}</LI>
                <LI>{t.rich("intro.diffItem5", { b: (chunks) => <b>{chunks}</b> })}</LI>
                <LI>{t.rich("intro.diffItem6", { b: (chunks) => <b>{chunks}</b> })}</LI>
              </UL>
              <Callout type="tip" title={t("intro.diffTipTitle")}>
                {t("intro.diffTipBody")}
              </Callout>
            </DocSection>
          </>
        ),
      },
      {
        id: "start",
        label: t("intro.startLabel"),
        content: (
          <>
            <DocSection title={t("intro.startTitle")}>
              <P>{t("intro.startLeadP")}</P>
              <Steps>
                <Step n={1}>
                  {t.rich("intro.startStep1", { b: (chunks) => <b>{chunks}</b> })}
                </Step>
                <Step n={2}>
                  {t.rich("intro.startStep2", { b: (chunks) => <b>{chunks}</b> })}
                </Step>
                <Step n={3}>
                  {t("intro.startStep3")}
                </Step>
                <Step n={4}>
                  {t("intro.startStep4")}
                </Step>
              </Steps>
            </DocSection>
            <DocSection title={t("intro.themeTitle")}>
              <P>
                {t("intro.themeBody")}
              </P>
            </DocSection>
          </>
        ),
      },
      {
        id: "balance",
        label: t("intro.balanceLabel"),
        content: (
          <>
            <DocSection title={t("intro.balanceTitle")}>
              <Lead>
                {t("intro.balanceLead")}
              </Lead>
              <UL>
                <LI>{t("intro.balanceItem1")}</LI>
                <LI>{t("intro.balanceItem2")}</LI>
                <LI>{t("intro.balanceItem3")}</LI>
                <LI>{t("intro.balanceItem4")}</LI>
              </UL>
            </DocSection>
            <DocSection title={t("intro.topupTitle")}>
              <FeatureGrid>
                <FeatureCard icon={<Wallet size={16} />} title={t("intro.topupCardTitle")}>
                  {t.rich("intro.topupCardBody", { a: (chunks) => <A href="/account/billing/">{chunks}</A> })}
                </FeatureCard>
                <FeatureCard icon={<Star size={16} />} title={t("intro.topupStarsTitle")}>
                  {t.rich("intro.topupStarsBody", { ic: (chunks) => <IC>{chunks}</IC> })}
                </FeatureCard>
              </FeatureGrid>
              <H3>{t("intro.topupH3")}</H3>
              <P>
                {t.rich("intro.topupTariffsP", { a: (chunks) => <A href="/account/billing/">{chunks}</A> })}
              </P>
              <Callout type="info" title={t("intro.topupPromoTitle")}>
                {t.rich("intro.topupPromoBody", { a: (chunks) => <A href="/account/referral/">{chunks}</A> })}
              </Callout>
            </DocSection>
          </>
        ),
      },
    ],
  },
  {
    title: t("chat.groupTitle"),
    items: [
      {
        id: "chat",
        label: t("chat.chatsLabel"),
        content: (
          <>
            <DocSection title={t("chat.chatTitle")} intro={t("chat.chatIntro")}>
              <FeatureGrid>
                <FeatureCard icon={<Zap size={16} />} title={t("chat.streamingTitle")}>
                  {t("chat.streamingBody")}
                </FeatureCard>
                <FeatureCard icon={<Search size={16} />} title={t("chat.webSearchTitle")}>
                  {t("chat.webSearchBody")}
                </FeatureCard>
                <FeatureCard icon={<FileText size={16} />} title={t("chat.attachmentsTitle")}>
                  {t("chat.attachmentsBody")}
                </FeatureCard>
                <FeatureCard icon={<Mic size={16} />} title={t("chat.voiceTitle")}>
                  {t("chat.voiceBody")}
                </FeatureCard>
              </FeatureGrid>
              <H3>{t("chat.historyH3")}</H3>
              <UL>
                <LI>{t("chat.historyItem1")}</LI>
                <LI>{t("chat.historyItem2")}</LI>
                <LI>{t.rich("chat.historyItem3", { b: (chunks) => <b>{chunks}</b> })}</LI>
                <LI>{t.rich("chat.historyItem4", { b: (chunks) => <b>{chunks}</b> })}</LI>
                <LI>{t("chat.historyItem5")}</LI>
              </UL>
              <Callout type="tip">
                {t.rich("chat.newChatTip", { ic: (chunks) => <IC>{chunks}</IC> })}
              </Callout>
            </DocSection>
          </>
        ),
      },
      {
        id: "models",
        label: t("chat.modelsLabel"),
        content: (
          <>
            <DocSection title={t("chat.modelsTitle")} intro={t("chat.modelsIntro")}>
              <P>{t("chat.modelsTabsP")}</P>
              <DataTable
                head={[t("chat.modelsTableType"), t("chat.modelsTableFor"), t("chat.modelsTableExamples")]}
                rows={[
                  [t("chat.modelsRowTextType"), t("chat.modelsRowTextFor"), <>{t("chat.modelsRowTextExamples")}</>],
                  [t("chat.modelsRowImgType"), t("chat.modelsRowImgFor"), <>{t("chat.modelsRowImgExamples")}</>],
                  [t("chat.modelsRowVideoType"), t("chat.modelsRowVideoFor"), <>{t("chat.modelsRowVideoExamples")}</>],
                ]}
              />
              <H3>{t("chat.modelsHowH3")}</H3>
              <UL>
                <LI>{t.rich("chat.modelsHowItem1", { b: (chunks) => <b>{chunks}</b> })}</LI>
                <LI>{t.rich("chat.modelsHowItem2", { b: (chunks) => <b>{chunks}</b> })}</LI>
                <LI>{t.rich("chat.modelsHowItem3", { b: (chunks) => <b>{chunks}</b> })}</LI>
              </UL>
              <P>
                {t.rich("chat.modelsSwitchP", {
                  ic: (chunks) => <IC>{chunks}</IC>,
                  a: (chunks) => <A href="/models/">{chunks}</A>,
                })}
              </P>
            </DocSection>
          </>
        ),
      },
      {
        id: "images",
        label: t("chat.imagesLabel"),
        content: (
          <DocSection title={t("chat.imagesTitle")} intro={t("chat.imagesIntro")}>
            <UL>
              <LI>{t.rich("chat.imagesItem1", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("chat.imagesItem2", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("chat.imagesItem3", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("chat.imagesItem4", { b: (chunks) => <b>{chunks}</b> })}</LI>
            </UL>
            <Callout type="info">
              {t.rich("chat.imagesFilesCallout", {
                a1: (chunks) => <A href="/account/files/">{chunks}</A>,
                a2: (chunks) => <A href="/account/favorites/">{chunks}</A>,
              })}
            </Callout>
            <Callout type="warn">
              {t("chat.imagesPaidWarn")}
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "video",
        label: t("chat.videoLabel"),
        content: (
          <DocSection title={t("chat.videoTitle")} intro={t("chat.videoIntro")}>
            <DataTable
              head={[t("chat.videoTableModel"), t("chat.videoTableFeatures")]}
              rows={[
                [t("chat.videoRowSoraModel"), t("chat.videoRowSoraFeatures")],
                [t("chat.videoRowVeoModel"), t("chat.videoRowVeoFeatures")],
                [t("chat.videoRowKlingModel"), t("chat.videoRowKlingFeatures")],
              ]}
            />
            <UL>
              <LI>{t.rich("chat.videoItem1", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("chat.videoItem2", { b: (chunks) => <b>{chunks}</b> })}</LI>
            </UL>
            <Callout type="tip">
              {t("chat.videoTip")}
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "compare",
        label: t("chat.compareLabel"),
        content: (
          <DocSection title={t("chat.compareTitle")} intro={t("chat.compareIntro")}>
            <UL>
              <LI>{t("chat.compareItem1")}</LI>
              <LI>{t("chat.compareItem2")}</LI>
              <LI>{t("chat.compareItem3")}</LI>
            </UL>
            <P>
              {t.rich("chat.compareLinksP", {
                a1: (chunks) => <A href="/compare/">{chunks}</A>,
                a2: (chunks) => <A href="/arena/">{chunks}</A>,
              })}
            </P>
          </DocSection>
        ),
      },
      {
        id: "prompts",
        label: t("chat.promptsLabel"),
        content: (
          <>
            <DocSection title={t("chat.promptsTitle")} intro={t("chat.promptsIntro")}>
              <UL>
                <LI>{t("chat.promptsItem1")}</LI>
                <LI>{t("chat.promptsItem2")}</LI>
              </UL>
              <P>{t.rich("chat.promptsLinkP", { a: (chunks) => <A href="/prompts/">{chunks}</A> })}</P>
            </DocSection>
            <DocSection title={t("chat.personasTitle")} intro={t("chat.personasIntro")}>
              <UL>
                <LI>{t("chat.personasItem1")}</LI>
                <LI>{t("chat.personasItem2")}</LI>
                <LI>{t.rich("chat.personasItem3", { ic: (chunks) => <IC>{chunks}</IC> })}</LI>
              </UL>
              <P>{t.rich("chat.personasLinkP", { a: (chunks) => <A href="/personas/">{chunks}</A> })}</P>
            </DocSection>
          </>
        ),
      },
    ],
  },
  {
    title: t("projects.groupTitle"),
    items: [
      {
        id: "projects",
        label: t("projects.projectsLabel"),
        content: (
          <DocSection title={t("projects.projectsTitle")} intro={t("projects.projectsIntro")}>
            <FeatureGrid>
              <FeatureCard icon={<FolderKanban size={16} />} title={t("projects.cardFolderTitle")}>
                {t("projects.cardFolderBody")}
              </FeatureCard>
              <FeatureCard icon={<FileText size={16} />} title={t("projects.cardKbTitle")}>
                {t("projects.cardKbBody")}
              </FeatureCard>
              <FeatureCard icon={<ScrollText size={16} />} title={t("projects.cardInstructionsTitle")}>
                {t("projects.cardInstructionsBody")}
              </FeatureCard>
              <FeatureCard icon={<Brain size={16} />} title={t("projects.cardMemoryTitle")}>
                {t("projects.cardMemoryBody")}
              </FeatureCard>
            </FeatureGrid>
            <P>{t.rich("projects.projectsOpenP", { a: (chunks) => <A href="/projects/">{chunks}</A> })}</P>
          </DocSection>
        ),
      },
      {
        id: "kb",
        label: t("projects.kbLabel"),
        content: (
          <DocSection title={t("projects.kbTitle")} intro={t("projects.kbIntro")}>
            <H3>{t("projects.kbUploadH3")}</H3>
            <P>{t("projects.kbUploadP")}</P>
            <H3>{t("projects.kbHowH3")}</H3>
            <UL>
              <LI>{t("projects.kbHowItem1")}</LI>
              <LI>{t("projects.kbHowItem2")}</LI>
              <LI>{t.rich("projects.kbHowItem3", { b: (chunks) => <b>{chunks}</b> })}</LI>
            </UL>
            <H3>{t("projects.kbCommandsH3")}</H3>
            <DataTable
              head={[t("projects.kbCommandsTableCommand"), t("projects.kbCommandsTableAction")]}
              rows={[
                [<IC>{t("projects.kbCmdFileIc")}</IC>, t("projects.kbCmdFileDesc")],
                [<IC>{t("projects.kbCmdWebIc")}</IC>, t("projects.kbCmdWebDesc")],
                [<IC>{t("projects.kbCmdCodebaseIc")}</IC>, t("projects.kbCmdCodebaseDesc")],
              ]}
            />
            <Callout type="tip" title={t("projects.kbDashboardTipTitle")}>
              {t("projects.kbDashboardTipBody")}
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "connectors",
        label: t("projects.connectorsLabel"),
        content: (
          <DocSection title={t("projects.connectorsTitle")} intro={t("projects.connectorsIntro")}>
            <FeatureGrid>
              <FeatureCard icon={<GitBranch size={16} />} title={t("projects.connectorsGitTitle")}>
                {t("projects.connectorsGitBody")}
              </FeatureCard>
              <FeatureCard icon={<Globe size={16} />} title={t("projects.connectorsSiteTitle")}>
                {t("projects.connectorsSiteBody")}
              </FeatureCard>
              <FeatureCard icon={<ScrollText size={16} />} title={t("projects.connectorsRssTitle")}>
                {t("projects.connectorsRssBody")}
              </FeatureCard>
            </FeatureGrid>
            <P>{t("projects.connectorsHowP")}</P>
          </DocSection>
        ),
      },
      {
        id: "code",
        label: t("projects.codeLabel"),
        content: (
          <DocSection title={t("projects.codeTitle")} intro={t("projects.codeIntro")}>
            <UL>
              <LI>{t.rich("projects.codeItem1", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("projects.codeItem2", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("projects.codeItem3", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t("projects.codeItem4")}</LI>
            </UL>
            <Callout type="info">
              {t("projects.codeAgentCallout")}
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "collab",
        label: t("projects.collabLabel"),
        content: (
          <>
            <DocSection title={t("projects.collabTitle")} intro={t("projects.collabIntro")}>
              <UL>
                <LI>{t.rich("projects.collabItem1", { b1: (chunks) => <b>{chunks}</b>, b2: (chunks) => <b>{chunks}</b> })}</LI>
                <LI>{t("projects.collabItem2")}</LI>
                <LI>{t.rich("projects.collabItem3", { b: (chunks) => <b>{chunks}</b> })}</LI>
              </UL>
            </DocSection>
            <DocSection title={t("projects.graphTitle")} intro={t("projects.graphIntro")}>
              <P>{t("projects.graphP")}</P>
            </DocSection>
          </>
        ),
      },
    ],
  },
  {
    title: t("smart.groupTitle"),
    items: [
      {
        id: "memory",
        label: t("smart.memoryLabel"),
        content: (
          <DocSection title={t("smart.memoryTitle")} intro={t("smart.memoryIntro")}>
            <H3>{t("smart.memoryLevelsH3")}</H3>
            <DataTable
              head={[t("smart.memoryTableLevel"), t("smart.memoryTableWhat"), t("smart.memoryTableWhere")]}
              rows={[
                [t("smart.memoryRowPersonalLevel"), t("smart.memoryRowPersonalWhat"), t("smart.memoryRowPersonalWhere")],
                [t("smart.memoryRowProjectLevel"), t("smart.memoryRowProjectWhat"), t("smart.memoryRowProjectWhere")],
                [t("smart.memoryRowTeamLevel"), t("smart.memoryRowTeamWhat"), t("smart.memoryRowTeamWhere")],
              ]}
            />
            <UL>
              <LI>{t("smart.memoryItem1")}</LI>
              <LI>{t("smart.memoryItem2")}</LI>
              <LI>{t("smart.memoryItem3")}</LI>
            </UL>
            <P>
              {t.rich("smart.memoryManageP", {
                a: (chunks) => <A href="/account/memory/">{chunks}</A>,
                ic: (chunks) => <IC>{chunks}</IC>,
              })}
            </P>
          </DocSection>
        ),
      },
      {
        id: "recall",
        label: t("smart.recallLabel"),
        content: (
          <DocSection title={t("smart.recallTitle")} intro={t("smart.recallIntro")}>
            <UL>
              <LI>{t("smart.recallItem1")}</LI>
              <LI>{t("smart.recallItem2")}</LI>
            </UL>
            <Callout type="info">
              {t("smart.recallCallout")}
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "research",
        label: t("smart.researchLabel"),
        content: (
          <DocSection title={t("smart.researchTitle")} intro={t("smart.researchIntro")}>
            <Steps>
              <Step n={1}>{t("smart.researchStep1")}</Step>
              <Step n={2}>{t("smart.researchStep2")}</Step>
              <Step n={3}>{t("smart.researchStep3")}</Step>
            </Steps>
            <UL>
              <LI>{t.rich("smart.researchItem1", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("smart.researchItem2", { ic: (chunks) => <IC>{chunks}</IC> })}</LI>
            </UL>
          </DocSection>
        ),
      },
      {
        id: "agent",
        label: t("smart.agentLabel"),
        content: (
          <DocSection title={t("smart.agentTitle")} intro={t("smart.agentIntro")}>
            <P>{t("smart.agentWhatP")}</P>
            <UL>
              <LI>{t.rich("smart.agentItem1", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("smart.agentItem2", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("smart.agentItem3", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("smart.agentItem4", { b: (chunks) => <b>{chunks}</b> })}</LI>
            </UL>
            <Callout type="tip" title={t("smart.agentCalloutTitle")}>
              {t.rich("smart.agentCalloutBody", { ic: (chunks) => <IC>{chunks}</IC> })}
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "tasks",
        label: t("smart.tasksLabel"),
        content: (
          <DocSection title={t("smart.tasksTitle")} intro={t("smart.tasksIntro")}>
            <UL>
              <LI>{t.rich("smart.tasksItem1", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("smart.tasksItem2", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("smart.tasksItem3", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("smart.tasksItem4", { b: (chunks) => <b>{chunks}</b> })}</LI>
            </UL>
            <P>
              {t.rich("smart.tasksCreateP", {
                ic: (chunks) => <IC>{chunks}</IC>,
                a: (chunks) => <A href="/account/tasks/">{chunks}</A>,
              })}
            </P>
            <Callout type="info">
              {t("smart.tasksCalloutBody")}
            </Callout>
          </DocSection>
        ),
      },
    ],
  },
  {
    title: t("account.groupTitle"),
    items: [
      {
        id: "account",
        label: t("account.accountLabel"),
        content: (
          <DocSection title={t("account.accountTitle")} intro={t("account.accountIntro")}>
            <DataTable
              head={[t("account.accountTableSection"), t("account.accountTableAction")]}
              rows={[
                [<A href="/account/">{t("account.rowOverviewLabel")}</A>, t("account.rowOverviewDesc")],
                [<A href="/account/analytics/">{t("account.rowAnalyticsLabel")}</A>, t("account.rowAnalyticsDesc")],
                [<A href="/account/billing/">{t("account.rowBillingLabel")}</A>, t("account.rowBillingDesc")],
                [<A href="/account/tasks/">{t("account.rowTasksLabel")}</A>, t("account.rowTasksDesc")],
                [<A href="/account/keys/">{t("account.rowKeysLabel")}</A>, t("account.rowKeysDesc")],
                [<A href="/account/referral/">{t("account.rowReferralLabel")}</A>, t("account.rowReferralDesc")],
                [<A href="/account/files/">{t("account.rowFilesLabel")}</A>, t("account.rowFilesDesc")],
                [<A href="/account/favorites/">{t("account.rowFavoritesLabel")}</A>, t("account.rowFavoritesDesc")],
                [<A href="/account/memory/">{t("account.rowMemoryLabel")}</A>, t("account.rowMemoryDesc")],
                [<A href="/account/telegram/">{t("account.rowTelegramLabel")}</A>, t("account.rowTelegramDesc")],
                [<A href="/account/oauth-apps/">{t("account.rowOauthLabel")}</A>, t("account.rowOauthDesc")],
              ]}
            />
          </DocSection>
        ),
      },
      {
        id: "settings",
        label: t("account.settingsLabel"),
        content: (
          <DocSection title={t("account.settingsTitle")} intro={t("account.settingsIntro")}>
            <UL>
              <LI>{t.rich("account.settingsItem1", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("account.settingsItem2", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("account.settingsItem3", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("account.settingsItem4", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("account.settingsItem5", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("account.settingsItem6", { b: (chunks) => <b>{chunks}</b> })}</LI>
            </UL>
          </DocSection>
        ),
      },
    ],
  },
  {
    title: t("telegram.groupTitle"),
    items: [
      {
        id: "tg-start",
        label: t("telegram.startLabel"),
        content: (
          <DocSection title={t("telegram.startTitle")} intro={t("telegram.startIntro")}>
            <Steps>
              <Step n={1}>{t.rich("telegram.startStep1", { a: (chunks) => <A href="https://t.me/aineron_bot">{chunks}</A> })}</Step>
              <Step n={2}>{t.rich("telegram.startStep2", { a: (chunks) => <A href="/account/telegram/">{chunks}</A> })}</Step>
              <Step n={3}>{t("telegram.startStep3")}</Step>
            </Steps>
            <Callout type="tip" title={t("telegram.startMenuTipTitle")}>
              {t("telegram.startMenuTipBody")}
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "tg-basic",
        label: t("telegram.basicLabel"),
        content: (
          <DocSection title={t("telegram.basicTitle")} intro={t("telegram.basicIntro")}>
            <DataTable
              head={[t("telegram.basicTableCommand"), t("telegram.basicTableAction")]}
              rows={[
                [<IC>{t("telegram.basicRowTextCommand")}</IC>, t("telegram.basicRowTextAction")],
                [<IC>{t("telegram.basicRowImageCommand")}</IC>, t("telegram.basicRowImageAction")],
                [<IC>{t("telegram.basicRowVideoCommand")}</IC>, t("telegram.basicRowVideoAction")],
                [<IC>{t("telegram.basicRowImg2videoCommand")}</IC>, t("telegram.basicRowImg2videoAction")],
                [<IC>{t("telegram.basicRowStickerCommand")}</IC>, t("telegram.basicRowStickerAction")],
                [<IC>{t("telegram.basicRowVoiceCommand")}</IC>, t("telegram.basicRowVoiceAction")],
                [<IC>{t("telegram.basicRowModelsCommand")}</IC>, t("telegram.basicRowModelsAction")],
                [<IC>{t("telegram.basicRowBalanceCommand")}</IC>, t("telegram.basicRowBalanceAction")],
                [<IC>{t("telegram.basicRowMemoryCommand")}</IC>, t("telegram.basicRowMemoryAction")],
                [<IC>{t("telegram.basicRowSettingsCommand")}</IC>, t("telegram.basicRowSettingsAction")],
                [<IC>{t("telegram.basicRowHelpCommand")}</IC>, t("telegram.basicRowHelpAction")],
              ]}
            />
            <P>{t("telegram.basicFilesP")}</P>
          </DocSection>
        ),
      },
      {
        id: "tg-agentic",
        label: t("telegram.agenticLabel"),
        content: (
          <DocSection title={t("telegram.agenticTitle")} intro={t("telegram.agenticIntro")}>
            <DataTable
              head={[t("telegram.agenticTableCommand"), t("telegram.agenticTableAction")]}
              rows={[
                [<IC>{t("telegram.agenticRowTaskCommand")}</IC>, t("telegram.agenticRowTaskAction")],
                [<IC>{t("telegram.agenticRowTasksCommand")}</IC>, t("telegram.agenticRowTasksAction")],
                [<IC>{t("telegram.agenticRowAgentCommand")}</IC>, t("telegram.agenticRowAgentAction")],
                [<IC>{t("telegram.agenticRowResearchCommand")}</IC>, t("telegram.agenticRowResearchAction")],
                [<IC>{t("telegram.agenticRowChannelCommand")}</IC>, t("telegram.agenticRowChannelAction")],
                [<IC>{t("telegram.agenticRowTopicsCommand")}</IC>, t("telegram.agenticRowTopicsAction")],
              ]}
            />
            <Callout type="tip" title={t("telegram.agenticCalloutTitle")}>
              {t("telegram.agenticCalloutBody")}
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "tg-business",
        label: t("telegram.businessLabel"),
        content: (
          <DocSection title={t("telegram.businessTitle")} intro={t("telegram.businessIntro")}>
            <UL>
              <LI>{t.rich("telegram.businessItem1", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("telegram.businessItem2", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("telegram.businessItem3", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("telegram.businessItem4", { b: (chunks) => <b>{chunks}</b> })}</LI>
            </UL>
            <P>
              {t.rich("telegram.businessFooterP", {
                ic: (chunks) => <IC>{chunks}</IC>,
                a: (chunks) => <A href="/business-bot/">{chunks}</A>,
              })}
            </P>
          </DocSection>
        ),
      },
      {
        id: "tg-more",
        label: t("telegram.moreLabel"),
        content: (
          <>
            <DocSection title={t("telegram.moreBotsTitle")} intro={t("telegram.moreBotsIntro")}>
              <UL>
                <LI>{t.rich("telegram.moreBotsItem1", { ic: (chunks) => <IC>{chunks}</IC> })}</LI>
                <LI>{t.rich("telegram.moreBotsItem2", { ic: (chunks) => <IC>{chunks}</IC> })}</LI>
                <LI>{t("telegram.moreBotsItem3")}</LI>
              </UL>
            </DocSection>
            <DocSection title={t("telegram.moreSubsTitle")}>
              <UL>
                <LI>{t.rich("telegram.moreSubsItem1", {
                  b: (chunks) => <b>{chunks}</b>,
                  ic1: (chunks) => <IC>{chunks}</IC>,
                  ic2: (chunks) => <IC>{chunks}</IC>,
                })}</LI>
                <LI>{t.rich("telegram.moreSubsItem2", { b: (chunks) => <b>{chunks}</b> })}</LI>
              </UL>
            </DocSection>
            <DocSection title={t("telegram.moreGroupsTitle")} intro={t("telegram.moreGroupsIntro")}>
              <UL>
                <LI>{t.rich("telegram.moreGroupsItem1", { ic: (chunks) => <IC>{chunks}</IC> })}</LI>
                <LI>{t.rich("telegram.moreGroupsItem2", { ic: (chunks) => <IC>{chunks}</IC> })}</LI>
                <LI>{t.rich("telegram.moreGroupsItem3", { ic: (chunks) => <IC>{chunks}</IC> })}</LI>
              </UL>
            </DocSection>
          </>
        ),
      },
      {
        id: "tg-miniapp",
        label: t("telegram.miniappLabel"),
        content: (
          <DocSection title={t("telegram.miniappTitle")} intro={t("telegram.miniappIntro")}>
            <UL>
              <LI>{t.rich("telegram.miniappItem1", {
                b1: (chunks) => <b>{chunks}</b>,
                b2: (chunks) => <b>{chunks}</b>,
                b3: (chunks) => <b>{chunks}</b>,
              })}</LI>
              <LI>{t("telegram.miniappItem2")}</LI>
              <LI>{t("telegram.miniappItem3")}</LI>
            </UL>
            <P>{t.rich("telegram.miniappFooterP", { ic: (chunks) => <IC>{chunks}</IC> })}</P>
          </DocSection>
        ),
      },
    ],
  },
  {
    title: t("teams.groupTitle"),
    items: [
      {
        id: "orgs",
        label: t("teams.orgsLabel"),
        content: (
          <DocSection title={t("teams.orgsTitle")} intro={t("teams.orgsIntro")}>
            <UL>
              <LI>{t.rich("teams.orgsItem1", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("teams.orgsItem2", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("teams.orgsItem3", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("teams.orgsItem4", { b: (chunks) => <b>{chunks}</b> })}</LI>
              <LI>{t.rich("teams.orgsItem5", { b: (chunks) => <b>{chunks}</b> })}</LI>
            </UL>
            <P>{t("teams.orgsFooterP")}</P>
          </DocSection>
        ),
      },
    ],
  },
  {
    title: t("help.groupTitle"),
    items: [
      {
        id: "faq",
        label: t("help.faqLabel"),
        content: (
          <DocSection title={t("help.faqTitle")}>
            <H3>{t("help.faqVpnQ")}</H3>
            <P>{t("help.faqVpnA")}</P>
            <H3>{t("help.faqBillingQ")}</H3>
            <P>{t("help.faqBillingA")}</P>
            <H3>{t("help.faqGenFailQ")}</H3>
            <P>{t("help.faqGenFailA")}</P>
            <H3>{t("help.faqDataQ")}</H3>
            <P>{t("help.faqDataA")}</P>
            <H3>{t("help.faqDiffQ")}</H3>
            <P>{t("help.faqDiffA")}</P>
            <H3>{t("help.faqApiQ")}</H3>
            <P>{t.rich("help.faqApiA", { a: (chunks) => <A href="/api-docs/">{chunks}</A> })}</P>
            <Callout type="info" title={t("help.faqCalloutTitle")}>
              {t("help.faqCalloutBody")}
            </Callout>
          </DocSection>
        ),
      },
    ],
  },
  ];
}

export default async function DocsPage() {
  const t = await getTranslations("docs");
  return (
    <DocLayout
      eyebrow={t("eyebrow")}
      title={t("pageTitle")}
      subtitle={t("subtitle")}
      breadcrumb={[{ label: t("breadcrumbHome"), href: "/" }, { label: t("breadcrumbDocs") }]}
      groups={buildGroups(t)}
    />
  );
}
