import api from './index'

export interface EncryptMetrics {
  entropy_original: number
  entropy_encrypted: number
  npcr: number
  uaci: number
}

export interface EncryptResponse {
  encrypted_image: string
  key: Record<string, any>
  metrics: EncryptMetrics
}

export interface DecryptResponse {
  decrypted_image: string
}

export const encryptApi = {
  async encrypt(
    imageFile: File,
    r: number = 3.9991,
    x0: number = 0.37291,
    n0: number = 500,
    rounds: number = 2
  ): Promise<EncryptResponse> {
    const formData = new FormData()
    formData.append('image', imageFile)
    formData.append('r', r.toString())
    formData.append('x0', x0.toString())
    formData.append('n0', n0.toString())
    formData.append('rounds', rounds.toString())

    const response = await api.post('/encrypt', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },

  async decrypt(
    imageFile: File,
    key: Record<string, any>
  ): Promise<DecryptResponse> {
    const formData = new FormData()
    formData.append('image', imageFile)
    formData.append('key', JSON.stringify(key))

    const response = await api.post('/encrypt/decrypt', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },

  async decryptDirect(
    imageFile: File,
    params: {
      r: number
      x0: number
      n0: number
      rounds: number
      H: number
      W: number
      C: number
    }
  ): Promise<DecryptResponse> {
    const formData = new FormData()
    formData.append('image', imageFile)
    formData.append('r', params.r.toString())
    formData.append('x0', params.x0.toString())
    formData.append('n0', params.n0.toString())
    formData.append('rounds', params.rounds.toString())
    formData.append('H', params.H.toString())
    formData.append('W', params.W.toString())
    formData.append('C', params.C.toString())

    const response = await api.post('/encrypt/decrypt/direct', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  }
}
