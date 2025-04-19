// Extract input data from Zapier using destructuring for cleaner code
const { inputHTML, newsletterTitle, headerImage, subtitle, postLink } =
  input_data;

/**
 * Populates an email template with content and styling optimized for email clients
 *
 * @param {string} contentHTML - The main HTML content for the newsletter
 * @param {string} newsletterTitle - The title of the newsletter
 * @param {string} headerImage - URL for the header image
 * @param {string} subtitle - Optional subtitle text
 * @param {string} postLink - URL to the original post
 * @returns {Object} Object containing the populated email HTML
 */
function populateEmailTemplate(
  contentHTML,
  newsletterTitle,
  headerImage,
  subtitle,
  postLink
) {
  // Basic input validation
  if (!contentHTML || !newsletterTitle) {
    console.error("Missing required inputs: content and title are required");
    return {
      populatedEmailHTML: "<p>Error: Missing required content</p>",
      error: "Missing required inputs: content and title are required",
    };
  }

  /**
   * Escapes HTML special characters to prevent injection issues
   * @param {string} unsafe - Potentially unsafe HTML content
   * @returns {string} Escaped HTML string
   */
  function escapeHTML(unsafe) {
    if (!unsafe) return "";

    return unsafe
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  /**
   * Prevents emojis from being italicized by wrapping them in normal style spans
   * @param {string} text - Text possibly containing emojis
   * @returns {string} Text with emojis wrapped in normal style spans
   */
  function unitalicizeEmojis(text) {
    if (!text) return "";

    // Regular expression to match emoji characters
    const emojiRegex =
      /[\p{Emoji_Presentation}\p{Emoji}\u{1F3FB}-\u{1F3FF}\u{1F9B0}-\u{1F9B3}]/gu;

    // Replace emojis with wrapped versions
    return text.replace(
      emojiRegex,
      (match) => `<span style="font-style: normal;">${match}</span>`
    );
  }

  /**
   * Adds necessary inline styles to HTML content for email compatibility
   * @param {string} html - Raw HTML content
   * @returns {string} HTML with inline styles added
   */
  function styleContent(html) {
    if (!html) return "";

    // Style images for email clients
    let styledHTML = html.replace(
      /<img/g,
      '<img style="max-width: 100%; height: auto; display: block; margin: 24px auto; border-radius: 1rem; border: 1px solid #333333;"'
    );

    // Style headings for consistency across email clients
    const headings = ["h1", "h2", "h3", "h4", "h5", "h6"];
    headings.forEach((tag) => {
      const regex = new RegExp(`<${tag}([^>]*)>`, "g");
      styledHTML = styledHTML.replace(regex, (match, attributes) => {
        return `<${tag}${attributes} style="font-family: Arial, sans-serif; margin: 24px 0 16px 0; line-height: 1.3;">`;
      });
    });

    // Style paragraphs for consistent spacing
    styledHTML = styledHTML.replace(/<p/g, '<p style="margin: 0 0 16px 0;"');

    return styledHTML;
  }

  // Prepare subtitle HTML if provided, otherwise use empty string
  const subtitleHTML = subtitle
    ? `<p style="font-family: Arial, sans-serif; font-size: 24px; font-style: italic; color: #17191a; margin: 0 0 16px 0; line-height: 1.3;">${unitalicizeEmojis(
        escapeHTML(subtitle)
      )}</p>`
    : "";

  // Email template HTML - designed for maximum email client compatibility
  const emailTemplate = `<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>✳️NEWSLETTER_TITLE✳️</title>
</head>
<body style="background-color: #ffffff; margin: 0 !important; padding: 0 !important; font-family: Georgia, serif; font-size: 18px; line-height: 1.5; color: #333333;">
    <div style="display: none; font-size: 1px; color: #fefefe; line-height: 1px; font-family: Georgia, serif; max-height: 0px; max-width: 0px; opacity: 0; overflow: hidden;">
        ✳️NEWSLETTER_TITLE✳️ - Your newsletter has arrived!
    </div>
    <!-- START CENTERED CONTAINER -->
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px;" align="center">
        <tr>
            <td align="center" valign="top">
                <!-- MARGIN WRAPPER -->
                <table border="0" cellpadding="4" cellspacing="0" width="100%" style="max-width: 600px;">
                    <tr>
                        <td>
                            <!-- START MAIN CONTENT AREA -->
                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #FFFFF5; border: 1px solid #333333;">
                                <!-- START HEADER AREA -->
                                <tr>
                                    <td align="center" valign="middle" style="padding: 20px; border-bottom: 1px solid #333333;">
                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                            <tr>
                                                <td width="50%" align="left" valign="middle">
                                                    <a href="https://www.koiibenvenutto.com/" target="_blank">
                                                        <img src="https://cdn.prod.website-files.com/66bfca27c52b542e8bae67c3/6704c9a84b9aa737d0db1ab0_KOii_dark.png" alt="KOii Logo" style="display: block; height: 24px; width: auto;" />
                                                    </a>
                                                </td>
                                                <td width="50%" align="right" valign="middle">
                                                    <span style="color: #333333; font-size: 32px; line-height: 32px; display: inline-block;">☁️🌲🤲 🔁</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                <!-- END HEADER AREA -->
                                <!-- START HEADER IMAGE AREA -->
                                <tr>
                                    <td align="center" valign="top" style="padding: 20px 20px 0 20px;">
                                        <img src="✳️HEADER_IMAGE✳️" alt="Header Image" style="max-width: 100%; height: auto; display: block; margin: 0 auto; border-radius: 1rem; border: 1px solid #333333;" />
                                    </td>
                                </tr>
                                <!-- END HEADER IMAGE AREA -->
                                <!-- START TITLE AND SUBTITLE -->
                                <tr>
                                    <td align="center" valign="top" style="padding: 20px 20px 0 20px; font-family: Arial, sans-serif;">
                                        <h1 style="margin: 0 0 16px 0; font-size: 28px; line-height: 1.3; color: #1B1B1B; font-weight: bold; font-family: Arial, sans-serif;">✳️NEWSLETTER_TITLE✳️</h1>
                                        ✳️SUBTITLE_PLACEHOLDER✳️
                                        <p style="font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #333333; margin: 16px 0 0 0;">
                                            <a href="✳️POST_LINK✳️" target="_blank" style="color: #03305c;">Read on website</a><br>
                                            Forwarded this email? <a href="https://www.koiibenvenutto.com/" target="_blank" style="color: #03305c;">Subscribe here</a>!
                                        </p>
                                    </td>
                                </tr>
                                <!-- END TITLE AND SUBTITLE -->
                                <tr>
                                    <td align="left" valign="top" style="padding: 20px; font-family: Georgia, serif; font-size: 18px; line-height: 1.5; color: #333333;">
                                        ✳️NEWSLETTER_CONTENT✳️
                                    </td>
                                </tr>
                                <!-- END MAIN CONTENT AREA -->
                            </table>
                        </td>
                    </tr>
                </table>
                <!-- END MARGIN WRAPPER -->
            </td>
        </tr>
    </table>
    <!-- END CENTERED CONTAINER -->
</body>
</html>`;

  // Populate the template with the input data using placeholders
  const populatedEmail = emailTemplate
    .replace(/✳️NEWSLETTER_TITLE✳️/g, escapeHTML(newsletterTitle))
    .replace("✳️HEADER_IMAGE✳️", headerImage || "")
    .replace("✳️SUBTITLE_PLACEHOLDER✳️", subtitleHTML)
    .replace("✳️POST_LINK✳️", postLink || "#")
    .replace("✳️NEWSLETTER_CONTENT✳️", styleContent(contentHTML));

  // Return the populated email HTML
  return {
    populatedEmailHTML: populatedEmail,
  };
}

// Populate the email template with the Zapier input data and return the result
return populateEmailTemplate(
  inputHTML,
  newsletterTitle,
  headerImage,
  subtitle,
  postLink
);
