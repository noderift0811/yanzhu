// 头像图片压缩：160×160 正方形 + JPEG 0.82。
// 项目默认零图片零 base64；这里是用户主动上传，压缩后约 8-20KB，
// 既能放进 SQLite 的 spec_json，也不会让导出的单文件 HTML 体积失控。
export const IMG_SIZE = 160;
export const IMG_QUALITY = 0.82;

export function compressImage(file) {
  return new Promise((resolve, reject) => {
    if (!file?.type?.startsWith("image/")) {
      reject(new Error("请选择图片文件"));
      return;
    }
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("读取图片失败"));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("图片解析失败"));
      img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = IMG_SIZE;
        canvas.height = IMG_SIZE;
        const ctx = canvas.getContext("2d");
        const side = Math.min(img.width, img.height);
        ctx.drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, IMG_SIZE, IMG_SIZE);
        resolve(canvas.toDataURL("image/jpeg", IMG_QUALITY));
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}
