import api from './index'

export interface EncodeMetrics {
  psnr_cover_stego: number
  ssim_cover_stego: number
}

export interface EncodeResponse {
  stego_image: string
  stego_key: string
  recovery_image: string
  metrics: EncodeMetrics
}

export interface DecodeResponse {
  secret_image: string
  mode: 'exact' | 'approximate'
}

export interface PipelineEncryptEncodeResponse {
  encrypted_secret: string
  stego_image: string
  chaos_key: Record<string, any>
  stego_key: string
  encrypt_metrics: {
    entropy_original: number
    entropy_encrypted: number
    npcr: number
    uaci: number
  }
  inn_metrics: EncodeMetrics
}

export interface PipelineDecodeDecryptResponse {
  extracted_encrypted: string
  decrypted_secret: string
  mode: 'exact' | 'approximate'
}

export const steganographyApi = {
  async encode(
    coverFile: File,
    secretFile: File,
    params: {
      modelName?: string
      forceReload?: boolean
    } = {}
  ): Promise<EncodeResponse> {
    const formData = new FormData()
    formData.append('cover', coverFile)
    formData.append('secret', secretFile)
    if (params.modelName) formData.append('model_name', params.modelName)
    if (params.forceReload) formData.append('force_reload', 'true')

    const response = await api.post('/steganography/encode', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },

  async decode(
    stegoFile: File,
    stegoKey?: string,
    params: {
      modelName?: string
      forceReload?: boolean
    } = {}
  ): Promise<DecodeResponse> {
    const formData = new FormData()
    formData.append('stego', stegoFile)
    if (stegoKey) {
      formData.append('stego_key', stegoKey)
    }
    if (params.modelName) formData.append('model_name', params.modelName)
    if (params.forceReload) formData.append('force_reload', 'true')

    const response = await api.post('/steganography/decode', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },

  async pipelineEncryptEncode(
    coverFile: File,
    secretFile: File,
    params: {
      r?: number
      x0?: number
      n0?: number
      rounds?: number
      modelName?: string
      forceReload?: boolean
    } = {}
  ): Promise<PipelineEncryptEncodeResponse> {
    const formData = new FormData()
    formData.append('cover', coverFile)
    formData.append('secret', secretFile)
    if (params.r) formData.append('r', params.r.toString())
    if (params.x0) formData.append('x0', params.x0.toString())
    if (params.n0) formData.append('n0', params.n0.toString())
    if (params.rounds) formData.append('rounds', params.rounds.toString())
    if (params.modelName) formData.append('model_name', params.modelName)
    if (params.forceReload) formData.append('force_reload', 'true')

    const response = await api.post('/steganography/pipeline/encrypt-encode', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },

  async pipelineDecodeDecrypt(
    stegoFile: File,
    params: {
      stegoKey?: string
      r?: number
      x0?: number
      n0?: number
      rounds?: number
      modelName?: string
      forceReload?: boolean
    } = {}
  ): Promise<PipelineDecodeDecryptResponse> {
    const formData = new FormData()
    formData.append('stego', stegoFile)
    if (params.stegoKey) formData.append('stego_key', params.stegoKey)
    if (params.r) formData.append('r', params.r.toString())
    if (params.x0) formData.append('x0', params.x0.toString())
    if (params.n0) formData.append('n0', params.n0.toString())
    if (params.rounds) formData.append('rounds', params.rounds.toString())
    if (params.modelName) formData.append('model_name', params.modelName)
    if (params.forceReload) formData.append('force_reload', 'true')

    const response = await api.post('/steganography/pipeline/decode-decrypt', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  }
}
