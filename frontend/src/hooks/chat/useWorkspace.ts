/*
 * This hook centralizes the chat workspace state.
 * It now coordinates four linked chains:
 * 1. Loading conversations and messages.
 * 2. Creating conversations and sending messages.
 * 3. Uploading pending attachments before message submission.
 * 4. Sending recorded audio to the backend and writing the transcript back into the draft.
 */

import { useEffect, useState } from "react";
import {
  ChatServiceError,
  buildConversationTitle,
  createPendingAttachment,
  createPromptSuggestions,
  createRemoteConversation,
  createSettingsMenuItems,
  getRemoteConversation,
  isChatSessionError,
  listRemoteConversations,
  mergeMessagesIntoConversation,
  removeRemoteAttachment,
  searchWorkspaceContent,
  sendAgentMessage,
  transcribeVoiceToText,
  uploadConversationAttachments,
  validateAttachmentSelection,
} from "../../services";
import type {
  AuthenticatedUser,
  ChatMessage,
  ChatConversation,
  Notice,
  PendingAttachment,
  PromptSuggestion,
  SettingsView,
  VoiceComposerState,
  WorkspaceSearchResult,
} from "../../types";

type UseWorkspaceOptions = {
  user: AuthenticatedUser;
  onUnauthorized?: () => void;
};

function formatOptimisticMessageTime(date: Date) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function getFileExtension(fileName: string) {
  const matchedExtension = fileName.match(/\.[^.]+$/)?.[0];
  return matchedExtension ?? "";
}

function createOptimisticUserMessage(
  content: string,
  attachments: PendingAttachment[],
): ChatMessage {
  const now = new Date();

  return {
    id: `optimistic-user-${now.getTime()}`,
    role: "user",
    content,
    createdAt: formatOptimisticMessageTime(now),
    status: "sending",
    messageType: "text",
    // Attachments may not have remote IDs yet, so use local IDs only for temporary rendering.
    // The optimistic message will be replaced by the backend message after upload + agent reply.
    attachments: attachments.map((attachment) => ({
      id: attachment.uploadedId ?? attachment.localId,
      name: attachment.name,
      extension: getFileExtension(attachment.name),
      mimeType: attachment.mimeType,
      size: attachment.size,
      kind: attachment.kind,
      parseStatus: attachment.status,
    })),
    extraMetadata: { optimistic: true },
  };
}

function removeMessageFromConversation(
  conversation: ChatConversation,
  messageId: string,
): ChatConversation {
  return {
    ...conversation,
    messages: conversation.messages.filter((message) => message.id !== messageId),
  };
}

function replaceOptimisticMessageInConversation(
  conversation: ChatConversation,
  optimisticMessageId: string,
  replacementMessages: ChatMessage[],
): ChatConversation {
  const withoutOptimisticMessage = removeMessageFromConversation(conversation, optimisticMessageId);
  return mergeMessagesIntoConversation(withoutOptimisticMessage, replacementMessages);
}

function toWorkspaceNotice(error: unknown): Notice {
  if (error instanceof ChatServiceError) {
    return {
      tone: "error",
      title: error.title,
      description: error.description,
    };
  }

  return {
    tone: "error",
    title: "加载失败",
    description: "处理主界面请求时发生异常，请稍后重试。",
  };
}

function upsertConversation(
  currentConversations: ChatConversation[],
  nextConversation: ChatConversation,
  moveToFront = false,
) {
  const conversationsWithoutTarget = currentConversations.filter(
    (conversation) => conversation.id !== nextConversation.id,
  );

  if (moveToFront) {
    return [nextConversation, ...conversationsWithoutTarget];
  }

  return [...conversationsWithoutTarget, nextConversation];
}

export function useWorkspace({ user, onUnauthorized }: UseWorkspaceOptions) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isSettingsMenuOpen, setIsSettingsMenuOpen] = useState(false);
  const [activeSettingsView, setActiveSettingsView] = useState<SettingsView | null>(null);
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
  const [draftInputSource, setDraftInputSource] = useState<"keyboard" | "voice">("keyboard");
  const [voiceComposerState, setVoiceComposerState] = useState<VoiceComposerState>("idle");
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [isSearchMenuOpen, setIsSearchMenuOpen] = useState(false);
  const [workspaceNotice, setWorkspaceNotice] = useState<Notice | null>(null);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [isUploadingAttachments, setIsUploadingAttachments] = useState(false);

  const settingsMenuItems = createSettingsMenuItems();
  const promptSuggestions = createPromptSuggestions();

  const activeConversation =
    conversations.find((conversation) => conversation.id === activeConversationId) ?? null;

  const searchResults = searchWorkspaceContent(searchKeyword, conversations, promptSuggestions);

  useEffect(() => {
    let isMounted = true;

    async function loadConversationList() {
      setIsLoadingConversations(true);
      setWorkspaceNotice(null);

      try {
        const remoteConversations = await listRemoteConversations();

        if (!isMounted) {
          return;
        }

        setConversations(remoteConversations);
      } catch (error) {
        if (!isMounted) {
          return;
        }

        if (isChatSessionError(error)) {
          onUnauthorized?.();
          return;
        }

        setWorkspaceNotice(toWorkspaceNotice(error));
      } finally {
        if (isMounted) {
          setIsLoadingConversations(false);
        }
      }
    }

    void loadConversationList();

    return () => {
      isMounted = false;
    };
  }, [user.publicId, onUnauthorized]);

  function toggleSidebar() {
    setIsSidebarOpen((currentState) => !currentState);
  }

  function toggleSettingsMenu() {
    setIsSettingsMenuOpen((currentState) => !currentState);
  }

  function closeSettingsMenu() {
    setIsSettingsMenuOpen(false);
  }

  function openSettingsView(view: SettingsView) {
    setActiveSettingsView(view);
    setIsSettingsMenuOpen(false);
  }

  function closeSettingsPanel() {
    setActiveSettingsView(null);
  }

  function updateSearchKeyword(nextKeyword: string) {
    setSearchKeyword(nextKeyword);
    setIsSearchMenuOpen(Boolean(nextKeyword.trim()));
  }

  function openSearchMenu() {
    if (searchKeyword.trim()) {
      setIsSearchMenuOpen(true);
    }
  }

  function closeSearchMenu() {
    setIsSearchMenuOpen(false);
  }

  function clearSearch() {
    setSearchKeyword("");
    setIsSearchMenuOpen(false);
  }

  function clearComposerState() {
    setDraft("");
    setPendingAttachments([]);
    setDraftInputSource("keyboard");
    setVoiceComposerState("idle");
    setVoiceError(null);
  }

  async function cleanupPendingRemoteAttachments(attachments: PendingAttachment[]) {
    const uploadedAttachmentIds = attachments
      .map((attachment) => attachment.uploadedId)
      .filter((attachmentId): attachmentId is string => Boolean(attachmentId));

    await Promise.allSettled(
      uploadedAttachmentIds.map((attachmentId) => removeRemoteAttachment(attachmentId)),
    );
  }

  function resetComposerState() {
    const attachmentsSnapshot = pendingAttachments;

    if (attachmentsSnapshot.some((attachment) => attachment.uploadedId)) {
      void cleanupPendingRemoteAttachments(attachmentsSnapshot);
    }

    clearComposerState();
  }

  async function openConversation(conversationId: string) {
    resetComposerState();
    setActiveConversationId(conversationId);
    setWorkspaceNotice(null);

    const targetConversation = conversations.find(
      (conversation) => conversation.id === conversationId,
    );

    if (targetConversation?.hasLoadedMessages) {
      return;
    }

    try {
      const remoteConversation = await getRemoteConversation(conversationId);

      setConversations((currentConversations) =>
        currentConversations.map((conversation) =>
          conversation.id === remoteConversation.id ? remoteConversation : conversation,
        ),
      );
    } catch (error) {
      if (isChatSessionError(error)) {
        onUnauthorized?.();
        return;
      }

      setWorkspaceNotice(toWorkspaceNotice(error));
    }
  }

  function startNewConversation() {
    resetComposerState();
    setActiveConversationId(null);
    setWorkspaceNotice(null);
    clearSearch();
  }

  function updateDraft(nextDraft: string) {
    setDraft(nextDraft);

    if (!nextDraft.trim()) {
      setDraftInputSource("keyboard");
    }
  }

  function addPendingFiles(fileList: FileList | File[]) {
    const files = Array.from(fileList);
    if (files.length === 0) {
      return;
    }

    try {
      validateAttachmentSelection(files, pendingAttachments.length);
      setPendingAttachments((currentAttachments) => [
        ...currentAttachments,
        ...files.map(createPendingAttachment),
      ]);
      setWorkspaceNotice(null);
    } catch (error) {
      setWorkspaceNotice(toWorkspaceNotice(error));
    }
  }

  function removePendingFile(localId: string) {
    const targetAttachment = pendingAttachments.find((attachment) => attachment.localId === localId);
    if (!targetAttachment) {
      return;
    }

    setPendingAttachments((currentAttachments) =>
      currentAttachments.filter((attachment) => attachment.localId !== localId),
    );

    if (targetAttachment.uploadedId) {
      void removeRemoteAttachment(targetAttachment.uploadedId).catch((error: unknown) => {
        setWorkspaceNotice(toWorkspaceNotice(error));
      });
    }
  }

  function handleVoiceRecordingChange(isRecording: boolean) {
    setVoiceComposerState(isRecording ? "recording" : "idle");
    setVoiceError(null);
  }

  async function transcribeRecordedAudio(audioBlob: Blob) {
    setVoiceComposerState("transcribing");
    setVoiceError(null);
    setWorkspaceNotice(null);

    try {
      const result = await transcribeVoiceToText(audioBlob);

      setDraft((currentDraft) =>
        currentDraft.trim() ? `${currentDraft.trim()} ${result.transcript}` : result.transcript,
      );
      setDraftInputSource("voice");
      setVoiceComposerState("idle");
    } catch (error) {
      setVoiceComposerState("error");
      setVoiceError(
        error instanceof ChatServiceError ? error.description : "语音转写失败，请稍后重试。",
      );
      setWorkspaceNotice(toWorkspaceNotice(error));
    }
  }

  function handleVoiceCaptureError(message: string) {
    setVoiceComposerState("error");
    setVoiceError(message);
  }

  async function sendMessage(promptFromSuggestion?: string) {
    const nextPrompt = (promptFromSuggestion ?? draft).trim();
    const hasAttachments = pendingAttachments.length > 0;
    const shouldClearTypedDraftImmediately = promptFromSuggestion === undefined;
    const draftSnapshot = draft;
    const draftInputSourceSnapshot = draftInputSource;

    if (
      (!nextPrompt && !hasAttachments) ||
      isSendingMessage ||
      isUploadingAttachments ||
      voiceComposerState === "transcribing"
    ) {
      return;
    }

    setWorkspaceNotice(null);
    setIsSendingMessage(true);
    if (shouldClearTypedDraftImmediately) {
      // Clear the controlled textarea before any network request starts.
      // Previously the draft was cleared only after `/agent/chat` returned, so the
      // text stayed visible while the agent was creating a conversation, uploading
      // attachments, and waiting for the model response. If the request fails, the
      // catch block restores this snapshot so the user does not lose their input.
      setDraft("");
      setDraftInputSource("keyboard");
      setVoiceError(null);
    }

    let targetConversationId = activeConversationId;
    let createdConversation: ChatConversation | null = null;
    let optimisticMessageId: string | null = null;

    try {
      if (!targetConversationId) {
        createdConversation = await createRemoteConversation(buildConversationTitle(nextPrompt));
        targetConversationId = createdConversation.id;

        setActiveConversationId(createdConversation.id);
        setConversations((currentConversations) =>
          upsertConversation(currentConversations, createdConversation!, true),
        );
      }

      const optimisticUserMessage = createOptimisticUserMessage(nextPrompt, pendingAttachments);
      optimisticMessageId = optimisticUserMessage.id;
      setConversations((currentConversations) => {
        const currentConversation =
          currentConversations.find((conversation) => conversation.id === targetConversationId) ??
          createdConversation;

        if (!currentConversation) {
          return currentConversations;
        }

        // Show the user's message immediately after the click, before slow work such as
        // attachment upload or model generation finishes. This keeps the chat timeline
        // responsive while the real backend messages are still being created.
        const nextConversation = mergeMessagesIntoConversation(currentConversation, [
          optimisticUserMessage,
        ]);

        return upsertConversation(currentConversations, nextConversation, true);
      });

      const alreadyUploadedAttachments = pendingAttachments.filter(
        (attachment) => attachment.uploadedId,
      );
      const attachmentsNeedingUpload = pendingAttachments.filter(
        (attachment) => !attachment.uploadedId,
      );

      let attachmentIds = alreadyUploadedAttachments
        .map((attachment) => attachment.uploadedId)
        .filter((attachmentId): attachmentId is string => Boolean(attachmentId));

      if (attachmentsNeedingUpload.length > 0) {
        setIsUploadingAttachments(true);

        const uploadedAttachments = await uploadConversationAttachments(
          targetConversationId,
          attachmentsNeedingUpload.map((attachment) => attachment.file),
        );

        attachmentIds = [...attachmentIds, ...uploadedAttachments.map((attachment) => attachment.id)];

        setPendingAttachments((currentAttachments) => {
          const uploadedByLocalId = new Map(
            attachmentsNeedingUpload.map((attachment, index) => [
              attachment.localId,
              uploadedAttachments[index]?.id ?? null,
            ]),
          );

          return currentAttachments.map((attachment) =>
            uploadedByLocalId.has(attachment.localId)
              ? {
                  ...attachment,
                  status: "uploaded",
                  uploadedId: uploadedByLocalId.get(attachment.localId) ?? null,
                }
              : attachment,
          );
        });
      }

      const { userMessage, assistantMessage } = await sendAgentMessage(targetConversationId, {
        content: nextPrompt,
        attachmentIds,
        extraMetadata: {
          input_source: draftInputSource,
        },
      });

      setConversations((currentConversations) => {
        const currentConversation =
          currentConversations.find((conversation) => conversation.id === targetConversationId) ??
          createdConversation;

        if (!currentConversation) {
          return currentConversations;
        }

        const nextConversation = mergeMessagesIntoConversation(currentConversation, [
          userMessage,
          assistantMessage,
        ]);
        const reconciledConversation = optimisticMessageId
          ? replaceOptimisticMessageInConversation(currentConversation, optimisticMessageId, [
              userMessage,
              assistantMessage,
            ])
          : nextConversation;

        return upsertConversation(currentConversations, reconciledConversation, true);
      });

      clearComposerState();
      clearSearch();
    } catch (error) {
      if (optimisticMessageId) {
        setConversations((currentConversations) =>
          currentConversations.map((conversation) =>
            conversation.id === targetConversationId
              ? removeMessageFromConversation(conversation, optimisticMessageId!)
              : conversation,
          ),
        );
      }

      if (isChatSessionError(error)) {
        onUnauthorized?.();
        return;
      }

      setWorkspaceNotice(toWorkspaceNotice(error));
      if (shouldClearTypedDraftImmediately) {
        setDraft(draftSnapshot);
        setDraftInputSource(draftInputSourceSnapshot);
      }
    } finally {
      setIsSendingMessage(false);
      setIsUploadingAttachments(false);
    }
  }

  async function usePromptSuggestion(suggestion: PromptSuggestion) {
    await sendMessage(suggestion.prompt);
  }

  async function selectSearchResult(result: WorkspaceSearchResult) {
    if (result.kind === "conversation" && result.conversationId) {
      await openConversation(result.conversationId);
    }

    if (result.kind === "suggestion" && result.prompt) {
      await sendMessage(result.prompt);
    }

    clearSearch();
  }

  return {
    user,
    draft,
    pendingAttachments,
    conversations,
    activeConversation,
    isSidebarOpen,
    isSettingsMenuOpen,
    activeSettingsView,
    settingsMenuItems,
    promptSuggestions,
    searchKeyword,
    isSearchMenuOpen,
    searchResults,
    workspaceNotice,
    isLoadingConversations,
    isSendingMessage,
    isUploadingAttachments,
    voiceComposerState,
    voiceError,
    toggleSidebar,
    toggleSettingsMenu,
    closeSettingsMenu,
    openSettingsView,
    closeSettingsPanel,
    updateSearchKeyword,
    openSearchMenu,
    closeSearchMenu,
    clearSearch,
    openConversation,
    startNewConversation,
    setDraft: updateDraft,
    updateDraft,
    addPendingFiles,
    removePendingFile,
    handleVoiceRecordingChange,
    handleVoiceCaptureError,
    transcribeRecordedAudio,
    sendMessage,
    usePromptSuggestion,
    selectSearchResult,
  };
}
