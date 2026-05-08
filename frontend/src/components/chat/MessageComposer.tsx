/*
 * Bottom composer for text, attachment, and voice input.
 * The component owns browser-only APIs such as MediaRecorder and file input clicks,
 * while the actual upload/transcription business flow remains in the workspace hook.
 */

import { useEffect, useRef, type ChangeEvent, type KeyboardEvent } from "react";
import { formatAttachmentSize } from "../../services";
import type { PendingAttachment, VoiceComposerState } from "../../types";
import {
  AttachmentIcon,
  CloseIcon,
  FileIcon,
  MicrophoneIcon,
  SendIcon,
  StopIcon,
} from "./WorkspaceIcons";

type MessageComposerProps = {
  value: string;
  attachments?: PendingAttachment[];
  isEmptyState: boolean;
  isSending?: boolean;
  isUploadingAttachments?: boolean;
  voiceState?: VoiceComposerState;
  voiceError?: string | null;
  onChange: (value: string) => void;
  onSelectFiles?: (files: FileList | File[]) => void;
  onRemoveAttachment?: (localId: string) => void;
  onVoiceRecordingChange?: (isRecording: boolean) => void;
  onVoiceCaptureError?: (message: string) => void;
  onVoiceCaptured?: (audioBlob: Blob) => void | Promise<void>;
  onSubmit: () => void;
};

function pickRecorderMimeType() {
  if (typeof MediaRecorder === "undefined") {
    return "";
  }

  const preferredTypes = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return preferredTypes.find((mimeType) => MediaRecorder.isTypeSupported(mimeType)) ?? "";
}

export function MessageComposer({
  value,
  attachments = [],
  isEmptyState,
  isSending = false,
  isUploadingAttachments = false,
  voiceState = "idle",
  voiceError = null,
  onChange,
  onSelectFiles = () => undefined,
  onRemoveAttachment = () => undefined,
  onVoiceRecordingChange = () => undefined,
  onVoiceCaptureError = () => undefined,
  onVoiceCaptured = async () => undefined,
  onSubmit,
}: MessageComposerProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const isBusy =
    isSending || isUploadingAttachments || voiceState === "transcribing" || voiceState === "recording";
  const isSubmitDisabled = (!value.trim() && attachments.length === 0) || isBusy;

  useEffect(() => {
    return () => {
      const recorder = mediaRecorderRef.current;
      if (recorder && recorder.state !== "inactive") {
        recorder.stop();
      }

      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !isSubmitDisabled) {
      event.preventDefault();
      onSubmit();
    }
  }

  function handleAttachmentButtonClick() {
    fileInputRef.current?.click();
  }

  function handleFileInputChange(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files && event.target.files.length > 0) {
      onSelectFiles(event.target.files);
    }

    // Reset the native input so the same file can be chosen again after removal.
    event.currentTarget.value = "";
  }

  async function toggleVoiceCapture() {
    if (voiceState === "transcribing" || isSending || isUploadingAttachments) {
      return;
    }

    const activeRecorder = mediaRecorderRef.current;
    if (activeRecorder && activeRecorder.state !== "inactive") {
      activeRecorder.stop();
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      onVoiceCaptureError("当前浏览器不支持录音，请改用手动输入。");
      return;
    }

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = pickRecorderMimeType();
      const recorder = mimeType
        ? new MediaRecorder(mediaStream, { mimeType })
        : new MediaRecorder(mediaStream);

      chunksRef.current = [];
      mediaRecorderRef.current = recorder;
      mediaStreamRef.current = mediaStream;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onerror = () => {
        onVoiceRecordingChange(false);
        mediaStream.getTracks().forEach((track) => track.stop());
        mediaRecorderRef.current = null;
        mediaStreamRef.current = null;
        chunksRef.current = [];
        onVoiceCaptureError("录音过程中发生异常，请重新尝试。");
      };

      recorder.onstop = () => {
        onVoiceRecordingChange(false);

        const audioBlob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });

        mediaStream.getTracks().forEach((track) => track.stop());
        mediaRecorderRef.current = null;
        mediaStreamRef.current = null;
        chunksRef.current = [];

        if (audioBlob.size === 0) {
          onVoiceCaptureError("没有采集到有效语音，请重新录制。");
          return;
        }

        void onVoiceCaptured(audioBlob);
      };

      recorder.start();
      onVoiceRecordingChange(true);
    } catch {
      onVoiceCaptureError("未获得麦克风权限，无法开始录音。");
    }
  }

  return (
    <div className={`composer ${isEmptyState ? "composer--floating" : ""}`}>
      <input
        ref={fileInputRef}
        className="composer__file-input"
        type="file"
        multiple
        accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.jpg,.jpeg,.png,.webp"
        onChange={handleFileInputChange}
      />

      {attachments.length > 0 && (
        <div className="composer__attachments">
          {attachments.map((attachment) => (
            <div key={attachment.localId} className="composer-attachment">
              <span className="composer-attachment__icon">
                <FileIcon />
              </span>

              <div className="composer-attachment__copy">
                <strong>{attachment.name}</strong>
                <span>
                  {attachment.kind === "image" ? "图片" : "文档"} ·{" "}
                  {formatAttachmentSize(attachment.size)}
                  {attachment.status === "uploaded" ? " · 已上传" : ""}
                </span>
              </div>

              <button
                className="composer-attachment__remove"
                type="button"
                aria-label={`移除附件 ${attachment.name}`}
                onClick={() => onRemoveAttachment(attachment.localId)}
              >
                <CloseIcon />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="composer__body">
        <div className="composer__controls">
          <button
            className="composer__icon-button"
            type="button"
            aria-label="添加附件"
            onClick={handleAttachmentButtonClick}
            disabled={isBusy}
          >
            <AttachmentIcon />
          </button>

          <button
            className={`composer__icon-button ${
              voiceState === "recording" ? "composer__icon-button--recording" : ""
            }`}
            type="button"
            aria-label={voiceState === "recording" ? "结束录音" : "开始录音"}
            onClick={() => {
              void toggleVoiceCapture();
            }}
            disabled={voiceState === "transcribing" || isSending || isUploadingAttachments}
          >
            {voiceState === "recording" ? <StopIcon /> : <MicrophoneIcon />}
          </button>
        </div>

        <div className="composer__field">
          <textarea
            value={value}
            placeholder="开启您的美食之旅..."
            rows={1}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={handleKeyDown}
          />

          {(voiceState !== "idle" || voiceError || isUploadingAttachments) && (
            <div className="composer__status" aria-live="polite">
              {voiceState === "recording" && <span>录音中，点击红色按钮结束录音。</span>}
              {voiceState === "transcribing" && <span>语音转写中，请稍候...</span>}
              {isUploadingAttachments && <span>附件上传中，请稍候...</span>}
              {voiceError && <span className="composer__status composer__status--error">{voiceError}</span>}
            </div>
          )}
        </div>

        <button
          className="composer__send"
          type="button"
          onClick={onSubmit}
          aria-label={isSending ? "正在发送消息" : "发送消息"}
          disabled={isSubmitDisabled}
        >
          <SendIcon />
        </button>
      </div>
    </div>
  );
}
