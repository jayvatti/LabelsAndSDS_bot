import { mount } from 'svelte'
import './tempApp.css'
import App from './TempApp.svelte'

const app = mount(App, {
  target: document.getElementById('app'),
})

export default app
