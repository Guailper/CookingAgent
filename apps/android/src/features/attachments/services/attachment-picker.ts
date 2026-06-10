import * as DocumentPicker from "expo-document-picker";
import * as ImagePicker from "expo-image-picker";

export async function pickDocumentAttachment() {
  const result = await DocumentPicker.getDocumentAsync({
    copyToCacheDirectory: true,
    multiple: false,
    type: [
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/vnd.openxmlformats-officedocument.presentationml.presentation",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ],
  });

  return result.canceled ? null : result.assets[0];
}

export async function pickImageAttachment() {
  const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!permission.granted) {
    throw new Error("需要相册权限才能选择图片。");
  }

  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ["images"],
    quality: 0.9,
  });

  return result.canceled ? null : result.assets[0];
}
