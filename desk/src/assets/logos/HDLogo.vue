<template>
  <img :src="logoUrl" alt="NXERP" width="118" height="118" />
</template>

<script setup lang="ts">
// Served by the backend (helpdesk/public/nxerp_login), not by Vite. A bound src keeps the
// production build from trying to bundle it as an import, which fails because it isn't in desk/.
const logoUrl = "/assets/helpdesk/nxerp_login/images/nxerp-mark.png";
</script>
